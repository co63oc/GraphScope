/** Copyright 2020 Alibaba Group Holding Limited.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * 	http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "grape/serialization/out_archive.h"

#include "flex/engines/graph_db/database/single_vertex_insert_transaction.h"
#include "flex/engines/graph_db/database/transaction_utils.h"
#include "flex/engines/graph_db/database/version_manager.h"
#include "flex/engines/graph_db/database/wal/wal.h"
#include "flex/storages/rt_mutable_graph/mutable_property_fragment.h"
#include "flex/utils/property/types.h"

namespace gs {

SingleVertexInsertTransaction::SingleVertexInsertTransaction(
    MutablePropertyFragment& graph, Allocator& alloc, IWalWriter& logger,
    VersionManager& vm, timestamp_t timestamp)
    : graph_(graph),
      alloc_(alloc),
      logger_(logger),
      vm_(vm),
      timestamp_(timestamp) {
  arc_.Resize(sizeof(WalHeader));
}
SingleVertexInsertTransaction::~SingleVertexInsertTransaction() { Abort(); }

bool SingleVertexInsertTransaction::AddVertex(label_t label, const Any& id,
                                              const std::vector<Any>& props) {
  size_t arc_size = arc_.GetSize();
  arc_ << static_cast<uint8_t>(0) << label;
  serialize_field(arc_, id);
  const std::vector<PropertyType>& types =
      graph_.schema().get_vertex_properties(label);
  if (types.size() != props.size()) {
    arc_.Resize(arc_size);
    std::string label_name = graph_.schema().get_vertex_label_name(label);
    LOG(ERROR) << "Vertex [" << label_name
               << "] properties size not match, expected " << types.size()
               << ", but got " << props.size();
    return false;
  }
  int col_num = props.size();
  for (int col_i = 0; col_i != col_num; ++col_i) {
    auto& prop = props[col_i];
    if (prop.type != types[col_i]) {
      if (!(prop.type == PropertyType::kStringView &&
            types[col_i] == PropertyType::kStringMap)) {
        arc_.Resize(arc_size);
        std::string label_name = graph_.schema().get_vertex_label_name(label);
        LOG(ERROR) << "Vertex [" << label_name << "][" << col_i
                   << "] property type not match, expected " << types[col_i]
                   << ", but got " << prop.type;
        return false;
      }
    }
    serialize_field(arc_, prop);
  }
  added_vertex_id_ = id;
  added_vertex_label_ = label;
  return true;
}

bool SingleVertexInsertTransaction::AddEdge(label_t src_label, const Any& src,
                                            label_t dst_label, const Any& dst,
                                            label_t edge_label,
                                            const Any& prop) {
  vid_t src_vid, dst_vid;
  if (src == added_vertex_id_ && src_label == added_vertex_label_) {
    if (!graph_.get_lid(dst_label, dst, dst_vid)) {
      std::string label_name = graph_.schema().get_vertex_label_name(dst_label);
      LOG(ERROR) << "Destination vertex " << label_name << "["
                 << dst.to_string() << "] not found...";
      return false;
    }
    src_vid = std::numeric_limits<vid_t>::max();
  } else if (dst == added_vertex_id_ && dst_label == added_vertex_label_) {
    if (!graph_.get_lid(src_label, src, src_vid)) {
      std::string label_name = graph_.schema().get_vertex_label_name(src_label);
      LOG(ERROR) << "Source vertex " << label_name << "[" << src.to_string()
                 << "] not found...";
      return false;
    }
    dst_vid = std::numeric_limits<vid_t>::max();
  } else {
    if (!graph_.get_lid(dst_label, dst, dst_vid)) {
      std::string label_name = graph_.schema().get_vertex_label_name(dst_label);
      LOG(ERROR) << "Destination vertex " << label_name << "["
                 << dst.to_string() << "] not found...";
      return false;
    }
    if (!graph_.get_lid(src_label, src, src_vid)) {
      std::string label_name = graph_.schema().get_vertex_label_name(src_label);
      LOG(ERROR) << "Source vertex " << label_name << "[" << src.to_string()
                 << "] not found...";
      return false;
    }
  }
  if (prop.type != PropertyType::kRecord) {
    const PropertyType& type =
        graph_.schema().get_edge_property(src_label, dst_label, edge_label);
    if (prop.type != type) {
      std::string label_name = graph_.schema().get_edge_label_name(edge_label);
      LOG(ERROR) << "Edge property " << label_name
                 << " type not match, expected " << type << ", got "
                 << prop.type;
      return false;
    }
  } else {
    const auto& types =
        graph_.schema().get_edge_properties(src_label, dst_label, edge_label);
    if (prop.AsRecord().size() != types.size()) {
      std::string label_name = graph_.schema().get_edge_label_name(edge_label);
      LOG(ERROR) << "Edge property " << label_name
                 << " size not match, expected " << types.size() << ", got "
                 << prop.AsRecord().size();
      return false;
    }
    auto r = prop.AsRecord();
    for (size_t i = 0; i < r.size(); ++i) {
      if (r[i].type != types[i]) {
        std::string label_name =
            graph_.schema().get_edge_label_name(edge_label);
        LOG(ERROR) << "Edge property " << label_name
                   << " type not match, expected " << types[i] << ", got "
                   << r[i].type;
        return false;
      }
    }
  }
  arc_ << static_cast<uint8_t>(1) << src_label;
  serialize_field(arc_, src);
  arc_ << dst_label;
  serialize_field(arc_, dst);
  arc_ << edge_label;
  serialize_field(arc_, prop);
  parsed_endpoints_.push_back(src_vid);
  parsed_endpoints_.push_back(dst_vid);
  return true;
}

bool SingleVertexInsertTransaction::Commit() {
  if (timestamp_ == std::numeric_limits<timestamp_t>::max()) {
    return true;
  }
  if (arc_.GetSize() == sizeof(WalHeader)) {
    vm_.release_insert_timestamp(timestamp_);
    clear();
    return true;
  }
  auto* header = reinterpret_cast<WalHeader*>(arc_.GetBuffer());
  header->length = arc_.GetSize() - sizeof(WalHeader);
  header->type = 0;
  header->timestamp = timestamp_;

  if (!logger_.append(arc_.GetBuffer(), arc_.GetSize())) {
    LOG(ERROR) << "Failed to append wal log";
    Abort();
    return false;
  }
  ingestWal();

  vm_.release_insert_timestamp(timestamp_);
  clear();
  return true;
}

void SingleVertexInsertTransaction::Abort() {
  if (timestamp_ != std::numeric_limits<timestamp_t>::max()) {
    LOG(ERROR) << "aborting " << timestamp_
               << "-th transaction (single vertex insert)";
    vm_.release_insert_timestamp(timestamp_);
    clear();
  }
}

timestamp_t SingleVertexInsertTransaction::timestamp() const {
  return timestamp_;
}

void SingleVertexInsertTransaction::ingestWal() {
  grape::OutArchive arc;
  arc.SetSlice(arc_.GetBuffer() + sizeof(WalHeader),
               arc_.GetSize() - sizeof(WalHeader));
  const vid_t* vid_ptr = parsed_endpoints_.data();
  while (!arc.Empty()) {
    uint8_t op_type;
    arc >> op_type;
    if (op_type == 0) {
      Any temp;
      deserialize_oid(graph_, arc, temp);
      added_vertex_vid_ =
          graph_.add_vertex(added_vertex_label_, added_vertex_id_);
      graph_.get_vertex_table(added_vertex_label_)
          .ingest(added_vertex_vid_, arc);
    } else if (op_type == 1) {
      Any temp;
      label_t src_label, dst_label, edge_label;
      src_label = deserialize_oid(graph_, arc, temp);
      dst_label = deserialize_oid(graph_, arc, temp);

      arc >> edge_label;

      vid_t src_vid = *(vid_ptr++);
      if (src_vid == std::numeric_limits<vid_t>::max()) {
        src_vid = added_vertex_vid_;
      }
      vid_t dst_vid = *(vid_ptr++);
      if (dst_vid == std::numeric_limits<vid_t>::max()) {
        dst_vid = added_vertex_vid_;
      }

      graph_.IngestEdge(src_label, src_vid, dst_label, dst_vid, edge_label,
                        timestamp_, arc, alloc_);
    } else {
      LOG(FATAL) << "Unexpected op-" << static_cast<int>(op_type);
    }
  }
}

void SingleVertexInsertTransaction::clear() {
  arc_.Clear();
  arc_.Resize(sizeof(WalHeader));

  timestamp_ = std::numeric_limits<timestamp_t>::max();
}

}  // namespace gs
