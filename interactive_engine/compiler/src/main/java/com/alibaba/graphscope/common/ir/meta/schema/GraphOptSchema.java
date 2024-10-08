/*
 * Copyright 2020 Alibaba Group Holding Limited.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.alibaba.graphscope.common.ir.meta.schema;

import com.alibaba.graphscope.common.exception.FrontendException;
import com.alibaba.graphscope.groot.common.exception.TypeNotFoundException;
import com.alibaba.graphscope.groot.common.schema.api.GraphElement;
import com.alibaba.graphscope.proto.frontend.Code;

import org.apache.calcite.plan.RelOptCluster;
import org.apache.calcite.plan.RelOptPlanner;
import org.apache.calcite.plan.RelOptSchema;
import org.apache.calcite.plan.RelOptTable;
import org.apache.calcite.rel.type.RelDataTypeFactory;
import org.apache.commons.lang3.ObjectUtils;
import org.checkerframework.checker.nullness.qual.Nullable;

import java.util.List;
import java.util.Objects;

/**
 * Maintain a set of {@link RelOptTable} objects per query in compilation phase
 */
public class GraphOptSchema implements RelOptSchema {
    private RelOptCluster optCluster;
    private IrGraphSchema rootSchema;

    public GraphOptSchema(@Nullable RelOptCluster optCluster, IrGraphSchema rootSchema) {
        this.optCluster = optCluster;
        this.rootSchema = Objects.requireNonNull(rootSchema);
    }

    /**
     * @param tableName name of an entity or a relation,
     *                  i.e. the name of an entity can be denoted by ["person"]
     *                  and the name of a relation can be denoted by ["knows"]
     * @return
     * @throws Exception - if the given table is not found
     */
    @Override
    public RelOptTable getTableForMember(List<String> tableName) {
        ObjectUtils.requireNonEmpty(tableName);
        String labelName = tableName.get(0);
        try {
            GraphElement element = rootSchema.getElement(labelName);
            return createRelOptTable(tableName, element);
        } catch (TypeNotFoundException e) {
            throw new FrontendException(
                    Code.LABEL_NOT_FOUND, "Table '" + labelName + "' not found", e);
        }
    }

    private RelOptTable createRelOptTable(List<String> tableName, GraphElement element) {
        return new GraphOptTable(this, tableName, element);
    }

    /**
     * {@link RelDataTypeFactory} provides interfaces to create {@link org.apache.calcite.rel.type.RelDataType} in Calcite
     *
     * @return
     */
    @Override
    public RelDataTypeFactory getTypeFactory() {
        return this.optCluster.getTypeFactory();
    }

    public IrGraphSchema getRootSchema() {
        return this.rootSchema;
    }

    // used in optimizer

    @Override
    public void registerRules(RelOptPlanner relOptPlanner) {
        // do nothing
    }
}
