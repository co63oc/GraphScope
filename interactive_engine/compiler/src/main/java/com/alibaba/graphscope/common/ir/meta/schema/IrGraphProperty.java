/*
 *
 *  * Copyright 2020 Alibaba Group Holding Limited.
 *  *
 *  * Licensed under the Apache License, Version 2.0 (the "License");
 *  * you may not use this file except in compliance with the License.
 *  * You may obtain a copy of the License at
 *  *
 *  * http://www.apache.org/licenses/LICENSE-2.0
 *  *
 *  * Unless required by applicable law or agreed to in writing, software
 *  * distributed under the License is distributed on an "AS IS" BASIS,
 *  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  * See the License for the specific language governing permissions and
 *  * limitations under the License.
 *
 */

package com.alibaba.graphscope.common.ir.meta.schema;

import com.alibaba.graphscope.groot.common.schema.impl.DefaultGraphProperty;
import com.google.common.base.Objects;

import org.apache.calcite.rel.type.RelDataType;

public class IrGraphProperty extends DefaultGraphProperty {
    private final RelDataType relDataType;

    public IrGraphProperty(int id, String name, RelDataType relDataType) {
        super(id, name, new IrDataTypeConvertor.Groot(null, false).convert(relDataType));
        this.relDataType = relDataType;
    }

    public RelDataType getRelDataType() {
        return this.relDataType;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        if (!super.equals(o)) return false;
        IrGraphProperty that = (IrGraphProperty) o;
        return Objects.equal(relDataType, that.relDataType);
    }

    @Override
    public int hashCode() {
        return Objects.hashCode(super.hashCode(), relDataType);
    }
}
