#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 Alibaba Group Holding Limited. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Manage connections of the GraphScope store service."""

import base64
import json

import grpc
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal

from graphscope.framework.graph_schema import GraphSchema
from graphscope.framework.record import EdgeRecordKey
from graphscope.framework.record import VertexRecordKey
from graphscope.framework.record import to_write_requests_pb
from graphscope.proto import ddl_service_pb2
from graphscope.proto import ddl_service_pb2_grpc
from graphscope.proto import write_service_pb2
from graphscope.proto import write_service_pb2_grpc
from graphscope.proto.groot.sdk import client_service_pb2_grpc
from graphscope.proto.groot.sdk import model_pb2


class Graph:
    def __init__(self, graph_def, conn=None) -> None:
        self._schema = GraphSchema()
        self._schema.from_graph_def(graph_def)
        self._conn: Connection = conn
        self._schema._conn = conn

    def schema(self):
        return self._schema

    def insert_vertex(self, vertex: VertexRecordKey, properties: dict):
        return self.insert_vertices([[vertex, properties]])

    def insert_vertices(self, vertices: list):
        request = to_write_requests_pb("VERTEX", vertices, write_service_pb2.INSERT)
        return self._conn.batch_write(request)

    def update_vertex_properties(self, vertex: VertexRecordKey, properties: dict):
        request = to_write_requests_pb(
            "VERTEX", [[vertex, properties]], write_service_pb2.UPDATE
        )
        return self._conn.batch_write(request)

    def update_vertex_properties_batch(self, vertices: list):
        request = to_write_requests_pb("VERTEX", vertices, write_service_pb2.UPDATE)
        return self._conn.batch_write(request)

    def delete_vertex(self, vertex_pk: VertexRecordKey):
        return self.delete_vertices([vertex_pk])

    def delete_vertices(self, vertex_pks: list):
        request = to_write_requests_pb(
            "VERTEX", [[pk, {}] for pk in vertex_pks], write_service_pb2.DELETE
        )
        return self._conn.batch_write(request)

    def insert_edge(self, edge: EdgeRecordKey, properties: dict):
        return self.insert_edges([[edge, properties]])

    def insert_edges(self, edges: list):
        request = to_write_requests_pb("EDGE", edges, write_service_pb2.INSERT)
        return self._conn.batch_write(request)

    def update_edge_properties(self, edge: EdgeRecordKey, properties: dict):
        request = to_write_requests_pb(
            "EDGE", [[edge, properties]], write_service_pb2.UPDATE
        )
        return self._conn.batch_write(request)

    def update_edge_properties_batch(self, edges: list):
        request = to_write_requests_pb("EDGE", edges, write_service_pb2.UPDATE)
        return self._conn.batch_write(request)

    def delete_edge(self, edge: EdgeRecordKey):
        return self.delete_edges([edge])

    def delete_edges(self, edge_pks: list):
        request = to_write_requests_pb(
            "EDGE", [[pk, {}] for pk in edge_pks], write_service_pb2.DELETE
        )
        return self._conn.batch_write(request)


class Connection:
    def __init__(self, addr, gremlin_endpoint, username="", password="") -> None:
        self._addr = addr
        self._gremlin_endpoint = gremlin_endpoint
        options = self._get_channel_options()
        channel = grpc.insecure_channel(addr, options=options)
        self._ddl_service_stub = ddl_service_pb2_grpc.GrootDdlServiceStub(channel)
        self._write_service_stub = write_service_pb2_grpc.ClientWriteStub(channel)
        self._client_service_stub = client_service_pb2_grpc.ClientStub(channel)
        self._client_id = None
        self._metadata = self._encode_metadata(username, password)
        gremlin_url = f"ws://{self._gremlin_endpoint}/gremlin"
        self._conn = DriverRemoteConnection(
            gremlin_url, "g", username=username, password=password
        )

    def _get_channel_options(self):
        json_config = json.dumps(
            {
                "methodConfig": [
                    {
                        "name": [{"service": "gs.rpc.groot.GrootDdlService"}],
                        "retryPolicy": {
                            "maxAttempts": 5,
                            "initialBackoff": "0.1s",
                            "maxBackoff": "10s",
                            "backoffMultiplier": 2,
                            "retryableStatusCodes": ["UNAVAILABLE"],
                        },
                    }
                ]
            }
        )

        options = [("grpc.service_config", json_config)]
        return options

    def __del__(self):
        self.close()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass  # be silent when closing

    def submit(self, requests):
        return self._ddl_service_stub.batchSubmit(requests, metadata=self._metadata)

    def get_graph_def(self, requests):
        return self._ddl_service_stub.getGraphDef(requests, metadata=self._metadata)

    def g(self):
        request = ddl_service_pb2.GetGraphDefRequest()
        graph_def = self.get_graph_def(request).graph_def
        graph = Graph(graph_def, self)
        return graph

    def gremlin(self):
        return traversal().withRemote(self._conn)

    def _get_client_id(self):
        if self._client_id is None:
            request = write_service_pb2.GetClientIdRequest()
            response = self._write_service_stub.getClientId(
                request, metadata=self._metadata
            )
            self._client_id = response.client_id
        return self._client_id

    def batch_write(self, request):
        request.client_id = self._get_client_id()
        response = self._write_service_stub.batchWrite(request, metadata=self._metadata)
        return response.snapshot_id

    def remote_flush(self, snapshot_id, timeout_ms=3000):
        request = write_service_pb2.RemoteFlushRequest()
        request.snapshot_id = snapshot_id
        request.wait_time_ms = timeout_ms
        response = self._write_service_stub.remoteFlush(
            request, metadata=self._metadata
        )
        return response.success

    def get_store_state(self):
        request = model_pb2.GetStoreStateRequest()
        response = self._client_service_stub.getStoreState(
            request, metadata=self._metadata
        )
        return response.partitionStates

    def replay_records(self, offset: int, timestamp: int):
        request = write_service_pb2.ReplayRecordsRequest()
        request.offset = offset
        request.timestamp = timestamp
        response = self._write_service_stub.replayRecords(
            request, metadata=self._metadata
        )
        return response.snapshot_id

    def compact_db(self):
        request = model_pb2.CompactDBRequest()
        response = self._client_service_stub.compactDB(request, metadata=self._metadata)
        return response.success

    def reopen_secondary(self):
        request = model_pb2.ReopenSecondaryRequest()
        response = self._client_service_stub.reopenSecondary(
            request, metadata=self._metadata
        )
        return response.success

    def replay_records_v2(self, offset: int, timestamp: int):
        request = model_pb2.ReplayRecordsRequestV2()
        request.offset = offset
        request.timestamp = timestamp
        response = self._client_service_stub.replayRecordsV2(
            request, metadata=self._metadata
        )
        return response.snapshot_id

    def _encode_metadata(self, username, password):
        if not (username and password):
            return None
        secret = username + ":" + password
        secret = base64.b64encode(secret.encode("utf-8", errors="ignore")).decode(
            "utf-8", errors="ignore"
        )
        metadata = [("authorization", "Basic " + secret)]
        return metadata


def conn(addr, gremlin_endpoint, username="", password=""):
    return Connection(addr, gremlin_endpoint, username, password)
