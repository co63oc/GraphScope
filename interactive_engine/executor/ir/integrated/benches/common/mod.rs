//
//! Copyright 2023 Alibaba Group Holding Limited.
//!
//! Licensed under the Apache License, Version 2.0 (the "License");
//! you may not use this file except in compliance with the License.
//! You may obtain a copy of the License at
//!
//! http://www.apache.org/licenses/LICENSE-2.0
//!
//! Unless required by applicable law or agreed to in writing, software
//! distributed under the License is distributed on an "AS IS" BASIS,
//! WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//! See the License for the specific language governing permissions and
//! limitations under the License.
//!

#[cfg(test)]
#[allow(dead_code)]
#[allow(unused_imports)]
pub mod benchmark {

    use std::collections::HashMap;
    use std::convert::{TryFrom, TryInto};
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::{Arc, Once};

    use graph_proxy::apis::{register_graph, DynDetails, Edge, PegasusClusterInfo, Vertex, ID};
    use graph_proxy::{create_exp_store, SimplePartition};
    use ir_common::expr_parse::str_to_expr_pb;
    use ir_common::generated::algebra as pb;
    use ir_common::generated::common as common_pb;
    use ir_common::generated::results as result_pb;
    use ir_common::{KeyId, LabelId, NameOrId};
    use lazy_static::lazy_static;
    use pegasus::result::{ResultSink, ResultStream};
    use pegasus::{run_opt, Configuration, JobConf, StartupError};
    use pegasus_server::job::{JobAssembly, JobDesc};
    use pegasus_server::rpc::RpcSink;
    use pegasus_server::JobRequest;
    use prost::Message;
    use runtime::process::entry::DynEntry;
    use runtime::process::record::Record;
    use runtime::IRJobAssembly;

    pub const TAG_A: KeyId = 0;
    pub const TAG_B: KeyId = 1;
    pub const TAG_C: KeyId = 2;
    pub const TAG_D: KeyId = 3;
    pub const TAG_E: KeyId = 4;
    pub const TAG_F: KeyId = 5;
    pub const TAG_G: KeyId = 6;
    pub const TAG_H: KeyId = 7;

    pub const PERSON_LABEL: LabelId = 1;
    pub const KNOWS_LABEL: LabelId = 12;

    static INIT: Once = Once::new();
    pub static JOB_ID: AtomicUsize = AtomicUsize::new(0);

    lazy_static! {
        static ref FACTORY: IRJobAssembly<SimplePartition, PegasusClusterInfo> = initialize_job_assembly();
    }

    pub fn initialize() {
        INIT.call_once(|| {
            start_pegasus();
        });
    }

    fn start_pegasus() {
        match pegasus::startup(Configuration::singleton()) {
            Ok(_) => {
                lazy_static::initialize(&FACTORY);
            }
            Err(err) => match err {
                StartupError::AlreadyStarted(_) => {}
                _ => panic!("start pegasus failed"),
            },
        }
    }

    fn initialize_job_assembly() -> IRJobAssembly<SimplePartition, PegasusClusterInfo> {
        let cluster_info = Arc::new(PegasusClusterInfo::default());
        let exp_store = create_exp_store(cluster_info.clone());
        register_graph(exp_store);
        let partition_info = Arc::new(SimplePartition { num_servers: 1 });
        IRJobAssembly::with(partition_info, cluster_info)
    }

    pub fn incr_request_job_id(job_req: &mut JobRequest) -> u64 {
        let mut conf = job_req.conf.take().expect("no job_conf");
        conf.job_id = JOB_ID.fetch_add(1, Ordering::SeqCst) as u64;
        let job_id = conf.job_id;
        job_req.conf = Some(conf);
        job_id
    }

    pub fn submit_query(job_req: JobRequest, num_workers: u32) -> ResultStream<Vec<u8>> {
        let mut conf = JobConf::default();
        conf.workers = num_workers;
        let (tx, rx) = crossbeam_channel::unbounded();
        let sink = ResultSink::new(tx);
        let cancel_hook = sink.get_cancel_hook().clone();
        let results = ResultStream::new(conf.job_id, cancel_hook, rx);
        let service = &FACTORY;
        let job = JobDesc { input: job_req.source, plan: job_req.plan, resource: job_req.resource };
        run_opt(conf, sink, move |worker| service.assemble(&job, worker)).expect("submit job failure;");
        results
    }

    pub fn parse_result(result: Vec<u8>) -> Option<Record> {
        let result: result_pb::Results = result_pb::Results::decode(result.as_slice()).unwrap();
        if let Some(result_pb::results::Inner::Record(record_pb)) = result.inner {
            let mut record = Record::default();
            for column in record_pb.columns {
                let tag: Option<KeyId> = if let Some(tag) = column.name_or_id {
                    match tag.item.unwrap() {
                        common_pb::name_or_id::Item::Name(name) => Some(
                            name.parse::<KeyId>()
                                .unwrap_or(KeyId::max_value()),
                        ),
                        common_pb::name_or_id::Item::Id(id) => Some(id),
                    }
                } else {
                    None
                };
                let entry = column.entry.unwrap();
                // append entry without moving head
                if let Some(tag) = tag {
                    let columns = record.get_columns_mut();
                    columns.insert(tag as usize, DynEntry::try_from(entry).unwrap());
                } else {
                    record.append(DynEntry::try_from(entry).unwrap(), None);
                }
            }
            Some(record)
        } else {
            None
        }
    }

    pub fn query_params(
        tables: Vec<common_pb::NameOrId>, columns: Vec<common_pb::NameOrId>,
        predicate: Option<common_pb::Expression>,
    ) -> pb::QueryParams {
        pb::QueryParams {
            tables,
            columns,
            is_all_columns: false,
            limit: None,
            predicate,
            sample_ratio: 1.0,
            extra: HashMap::new(),
        }
    }

    pub fn query_params_all_columns(
        tables: Vec<common_pb::NameOrId>, columns: Vec<common_pb::NameOrId>,
        predicate: Option<common_pb::Expression>,
    ) -> pb::QueryParams {
        pb::QueryParams {
            tables,
            columns,
            is_all_columns: true,
            limit: None,
            predicate,
            sample_ratio: 1.0,
            extra: HashMap::new(),
        }
    }

    pub fn to_var_pb(tag: Option<NameOrId>, key: Option<NameOrId>) -> common_pb::Variable {
        common_pb::Variable {
            tag: tag.map(|t| t.into()),
            property: key
                .map(|k| common_pb::Property { item: Some(common_pb::property::Item::Key(k.into())) }),
            node_type: None,
        }
    }

    pub fn to_expr_var_pb(tag: Option<NameOrId>, key: Option<NameOrId>) -> common_pb::Expression {
        common_pb::Expression {
            operators: vec![common_pb::ExprOpr {
                node_type: None,
                item: Some(common_pb::expr_opr::Item::Var(to_var_pb(tag, key))),
            }],
        }
    }

    pub fn to_expr_var_all_prop_pb(tag: Option<NameOrId>) -> common_pb::Expression {
        common_pb::Expression {
            operators: vec![common_pb::ExprOpr {
                node_type: None,
                item: Some(common_pb::expr_opr::Item::Var(common_pb::Variable {
                    tag: tag.map(|t| t.into()),
                    property: Some(common_pb::Property {
                        item: Some(common_pb::property::Item::All(common_pb::AllKey {})),
                    }),
                    node_type: None,
                })),
            }],
        }
    }

    pub fn to_expr_vars_pb(
        tag_keys: Vec<(Option<NameOrId>, Option<NameOrId>)>, is_map: bool,
    ) -> common_pb::Expression {
        let vars = tag_keys
            .into_iter()
            .map(|(tag, key)| to_var_pb(tag, key))
            .collect();
        common_pb::Expression {
            operators: vec![common_pb::ExprOpr {
                node_type: None,
                item: if is_map {
                    Some(common_pb::expr_opr::Item::VarMap(common_pb::VariableKeys { keys: vars }))
                } else {
                    Some(common_pb::expr_opr::Item::Vars(common_pb::VariableKeys { keys: vars }))
                },
            }],
        }
    }

    pub fn build_scan_with_predicate(
        tables: Vec<common_pb::NameOrId>, predicate: String, alias: Option<common_pb::NameOrId>,
    ) -> pb::Scan {
        pb::Scan {
            scan_opt: 0,
            alias,
            params: Some(query_params(tables, vec![], str_to_expr_pb(predicate).ok())),
            idx_predicate: None,
            meta_data: None,
            is_count_only: false,
        }
    }

    pub fn build_scan(tables: Vec<common_pb::NameOrId>, alias: Option<common_pb::NameOrId>) -> pb::Scan {
        pb::Scan {
            scan_opt: 0,
            alias,
            params: Some(query_params(tables, vec![], None)),
            idx_predicate: None,
            meta_data: None,
            is_count_only: false,
        }
    }

    pub fn build_expand_v(
        direction: i32, edge_labels: Vec<common_pb::NameOrId>, alias: Option<common_pb::NameOrId>,
    ) -> pb::EdgeExpand {
        pb::EdgeExpand {
            v_tag: None,
            direction,
            params: Some(query_params(edge_labels, vec![], None)),
            alias,
            expand_opt: 0,
            meta_data: None,
            is_optional: false,
        }
    }

    pub fn build_expand_v_from_tag(
        tag: Option<common_pb::NameOrId>, direction: i32, edge_labels: Vec<common_pb::NameOrId>,
        alias: Option<common_pb::NameOrId>,
    ) -> pb::EdgeExpand {
        pb::EdgeExpand {
            v_tag: tag,
            direction,
            params: Some(query_params(edge_labels, vec![], None)),
            alias,
            expand_opt: 0,
            meta_data: None,
            is_optional: false,
        }
    }

    pub fn build_as(alias: i32) -> pb::Project {
        pb::Project {
            mappings: vec![pb::project::ExprAlias {
                expr: str_to_expr_pb("@".to_string()).ok(),
                alias: Some(alias.into()),
            }],
            is_append: true,
            meta_data: vec![],
        }
    }

    pub fn build_order(
        order_pair: Vec<(Option<NameOrId>, Option<NameOrId>, pb::order_by::ordering_pair::Order)>,
        limit: Option<i32>,
    ) -> pb::OrderBy {
        let pairs = order_pair
            .into_iter()
            .map(|(tag, var, order)| {
                let key = to_var_pb(tag, var);
                pb::order_by::OrderingPair { key: Some(key), order: order as i32 }
            })
            .collect();
        let limit = limit.map(|upper| pb::Range { lower: 0, upper });
        pb::OrderBy { pairs, limit }
    }

    pub fn default_count_pb() -> pb::GroupBy {
        pb::GroupBy {
            mappings: vec![],
            functions: vec![pb::group_by::AggFunc {
                vars: vec![],
                aggregate: 3, // count
                alias: None,
            }],
            meta_data: vec![],
        }
    }

    pub fn default_sink_pb() -> pb::Sink {
        pb::Sink { tags: vec![common_pb::NameOrIdKey { key: None }], sink_target: default_sink_target() }
    }

    pub fn default_sink_target() -> Option<pb::sink::SinkTarget> {
        Some(pb::sink::SinkTarget {
            inner: Some(pb::sink::sink_target::Inner::SinkDefault(pb::SinkDefault {
                id_name_mappings: vec![],
            })),
        })
    }
}
