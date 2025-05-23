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

package com.alibaba.graphscope.common.ir.planner;

import com.alibaba.graphscope.common.config.Configs;
import com.alibaba.graphscope.common.config.PlannerConfig;
import com.alibaba.graphscope.common.ir.meta.IrMeta;
import com.alibaba.graphscope.common.ir.meta.IrMetaStats;
import com.alibaba.graphscope.common.ir.meta.IrMetaTracker;
import com.alibaba.graphscope.common.ir.meta.glogue.calcite.GraphRelMetadataQuery;
import com.alibaba.graphscope.common.ir.meta.glogue.calcite.handler.GraphMetadataHandlerProvider;
import com.alibaba.graphscope.common.ir.meta.schema.CommonOptTable;
import com.alibaba.graphscope.common.ir.rel.CommonTableScan;
import com.alibaba.graphscope.common.ir.rel.GraphShuttle;
import com.alibaba.graphscope.common.ir.rel.graph.GraphLogicalSource;
import com.alibaba.graphscope.common.ir.rel.graph.match.AbstractLogicalMatch;
import com.alibaba.graphscope.common.ir.rel.graph.match.GraphLogicalMultiMatch;
import com.alibaba.graphscope.common.ir.rel.graph.match.GraphLogicalSingleMatch;
import com.alibaba.graphscope.common.ir.rel.metadata.glogue.Glogue;
import com.alibaba.graphscope.common.ir.rel.metadata.glogue.GlogueQuery;
import com.alibaba.graphscope.common.ir.rel.metadata.schema.GlogueSchema;
import com.alibaba.graphscope.common.ir.tools.GraphBuilderFactory;
import com.alibaba.graphscope.common.ir.tools.config.GraphOpt;
import com.google.common.base.Preconditions;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

import org.apache.calcite.plan.GraphOptCluster;
import org.apache.calcite.plan.RelOptPlanner;
import org.apache.calcite.rel.RelNode;
import org.apache.calcite.rel.RelVisitor;
import org.apache.calcite.rel.core.Filter;
import org.apache.calcite.rel.core.JoinRelType;
import org.apache.calcite.rel.logical.LogicalJoin;
import org.apache.calcite.rel.metadata.RelMetadataQuery;
import org.apache.calcite.tools.RelBuilderFactory;
import org.checkerframework.checker.nullness.qual.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.Closeable;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Optimize graph relational tree which consists of match and other relational operators
 */
public class GraphRelOptimizer implements Closeable, IrMetaTracker {
    private static final Logger logger = LoggerFactory.getLogger(GraphRelOptimizer.class);
    private final PlannerConfig config;
    private final RelBuilderFactory relBuilderFactory;
    private final PlannerGroupManager plannerGroupManager;

    private final AtomicReference<GlogueQuery> glogueRef;

    public GraphRelOptimizer(Configs graphConfig, Class<? extends PlannerGroupManager> instance) {
        try {
            this.config = new PlannerConfig(graphConfig);
            this.relBuilderFactory = new GraphBuilderFactory(graphConfig);
            this.plannerGroupManager =
                    instance.getDeclaredConstructor(PlannerConfig.class, RelBuilderFactory.class)
                            .newInstance(this.config, this.relBuilderFactory);
            this.glogueRef = new AtomicReference<>();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public GraphRelOptimizer(Configs graphConfig) {
        this(graphConfig, PlannerGroupManager.Dynamic.class);
    }

    public RelOptPlanner getMatchPlanner() {
        PlannerGroup currentGroup = this.plannerGroupManager.getCurrentGroup();
        return currentGroup.getMatchPlanner();
    }

    public RelNode optimize(RelNode before, GraphIOProcessor ioProcessor) {
        PlannerGroup currentGroup = this.plannerGroupManager.getCurrentGroup();
        return currentGroup.optimize(before, ioProcessor);
    }

    public @Nullable RelMetadataQuery createMetaDataQuery(IrMeta irMeta) {
        if (config.isOn() && config.getOpt() == PlannerConfig.Opt.CBO) {
            GlogueQuery gq = this.glogueRef.get();
            Preconditions.checkArgument(gq != null, "glogue is not ready");
            return new GraphRelMetadataQuery(
                    new GraphMetadataHandlerProvider(getMatchPlanner(), gq, this.config));
        }
        return null;
    }

    @Override
    public void close() {
        if (this.plannerGroupManager != null) {
            this.plannerGroupManager.close();
        }
    }

    @Override
    public void onSchemaChanged(IrMeta meta) {
        if (this.plannerGroupManager != null) {
            this.plannerGroupManager.clean();
        }
    }

    @Override
    public void onStatsChanged(IrMetaStats stats) {
        GlogueSchema g = GlogueSchema.fromMeta(stats);
        Glogue gl = new Glogue(g, config.getGlogueSize());
        GlogueQuery gq = new GlogueQuery(gl);
        this.glogueRef.compareAndSet(glogueRef.get(), gq);
    }

    public static class MatchOptimizer extends GraphShuttle {
        private final GraphIOProcessor ioProcessor;
        private final RelOptPlanner matchPlanner;
        // record the common rel(s) which has been optimized
        private final Map<String, RelNode> commonTableToOpt;

        public MatchOptimizer(GraphIOProcessor ioProcessor, RelOptPlanner matchPlanner) {
            this.ioProcessor = ioProcessor;
            this.matchPlanner = matchPlanner;
            this.commonTableToOpt = Maps.newHashMap();
        }

        @Override
        public RelNode visit(CommonTableScan tableScan) {
            CommonOptTable optTable = (CommonOptTable) tableScan.getTable();
            String tableName = optTable.getQualifiedName().get(0);
            RelNode commonOpt = commonTableToOpt.get(tableName);
            if (commonOpt == null) {
                commonOpt = optTable.getCommon().accept(this);
                commonTableToOpt.put(tableName, commonOpt);
            }
            return new CommonTableScan(
                    tableScan.getCluster(), tableScan.getTraitSet(), new CommonOptTable(commonOpt));
        }

        @Override
        public RelNode visit(GraphLogicalSingleMatch match) {
            matchPlanner.setRoot(ioProcessor.processInput(match));
            return ioProcessor.processOutput(matchPlanner.findBestExp());
        }

        @Override
        public RelNode visit(GraphLogicalMultiMatch match) {
            matchPlanner.setRoot(ioProcessor.processInput(match));
            return ioProcessor.processOutput(matchPlanner.findBestExp());
        }

        @Override
        public RelNode visit(LogicalJoin join) {
            List<RelNode> matchList = Lists.newArrayList();
            List<RelNode> filterList = Lists.newArrayList();
            if (!decomposeJoin(join, matchList, filterList)) {
                return super.visit(join);
            } else {
                matchPlanner.setRoot(ioProcessor.processInput(matchList));
                RelNode match = ioProcessor.processOutput(matchPlanner.findBestExp());
                for (RelNode filter : filterList) {
                    match = filter.copy(filter.getTraitSet(), ImmutableList.of(match));
                }
                return match;
            }
        }

        private boolean decomposeJoin(
                LogicalJoin join, List<RelNode> matchList, List<RelNode> filterList) {
            AtomicBoolean decomposable = new AtomicBoolean(true);
            RelVisitor visitor =
                    new RelVisitor() {
                        @Override
                        public void visit(RelNode node, int ordinal, @Nullable RelNode parent) {
                            if (node instanceof LogicalJoin) {
                                JoinRelType joinType = ((LogicalJoin) node).getJoinType();
                                if (joinType != JoinRelType.LEFT && joinType != JoinRelType.INNER) {
                                    decomposable.set(false);
                                    return;
                                }
                                visit(((LogicalJoin) node).getLeft(), 0, node);
                                if (!decomposable.get()) {
                                    return;
                                }
                                int leftMatchSize = matchList.size();
                                visit(((LogicalJoin) node).getRight(), 1, node);
                                if (!decomposable.get()) {
                                    return;
                                }
                                if (joinType == JoinRelType.LEFT) {
                                    for (int i = leftMatchSize; i < matchList.size(); i++) {
                                        if (matchList.get(i) instanceof GraphLogicalSingleMatch) {
                                            GraphLogicalSingleMatch singleMatch =
                                                    (GraphLogicalSingleMatch) matchList.get(i);
                                            matchList.set(
                                                    i,
                                                    GraphLogicalSingleMatch.create(
                                                            (GraphOptCluster)
                                                                    singleMatch.getCluster(),
                                                            ImmutableList.of(),
                                                            singleMatch.getInput(),
                                                            singleMatch.getSentence(),
                                                            GraphOpt.Match.OPTIONAL));
                                        }
                                    }
                                }
                            } else if (node instanceof AbstractLogicalMatch) {
                                matchList.add(node);
                            } else if (node instanceof GraphLogicalSource) {
                                matchList.add(
                                        GraphLogicalSingleMatch.create(
                                                (GraphOptCluster) node.getCluster(),
                                                ImmutableList.of(),
                                                null,
                                                node,
                                                GraphOpt.Match.INNER));
                            } else if (node instanceof Filter) {
                                filterList.add(node);
                                visit(node.getInput(0), 0, node);
                            } else {
                                decomposable.set(false);
                            }
                        }
                    };
            visitor.go(join);
            return decomposable.get();
        }
    }
}
