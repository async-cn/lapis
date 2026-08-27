from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

def try_to_node(obj):
    if hasattr(obj, "to_node"):
        return obj.to_node()
    else:
        return obj

# region 所有抽象运算符类

class ASTOperator(ABC):
    operator_type:str
    operator_name:str
    def to_node(self) -> dict[str, Any]:
        return {
            "op_type":self.operator_type,
            "op_name":self.operator_name
        }

class LogicOperator(ASTOperator):
    operator_type:str = "logic"

class UnaryLogicOperator(LogicOperator):
    def __init__(self, a:ASTOperator):
        self.a = a
    def to_node(self) -> dict[str, Any]:
        return {**super().to_node(), 'a': self.a.to_node()}

class BinaryLogicOperator(LogicOperator):
    def __init__(self, a:ASTOperator, b:ASTOperator):
        self.a = a
        self.b = b
    def to_node(self) -> dict[str, Any]:
        return {**super().to_node(), 'a': self.a.to_node(), 'b': self.b.to_node()}

class MultiLogicOperator(LogicOperator):
    def __init__(self, *operands:ASTOperator):
        self.operands = operands
    def to_node(self) -> dict[str, Any]:
        return {**super().to_node(), 'operands': [op.to_node() for op in self.operands]}

class ConditionOperator(ASTOperator):
    operator_type:str = "condition"

class UnaryConditionOperator(ConditionOperator):
    def __init__(self, a:str):
        self.a = a
    def to_node(self) -> dict[str, Any]:
        return {
            **super().to_node(),
            'a': try_to_node(self.a)
        }

class BinaryConditionOperator(ConditionOperator):
    def __init__(self, a:str, b:Any):
        self.a = a
        self.b = b
    def to_node(self) -> dict[str, Any]:
        return {**super().to_node(),
            'a': try_to_node(self.a),
            'b': try_to_node(self.b)
        }

class SpecialConditionOperator(ConditionOperator):
    operator_type:str = "special_condition"
    pass

# endregion

# region 空运算符
class VoidOperator(ASTOperator):
    operator_type:str = "void"
    def __init__(self):
        self.operator_name = "void"

# region 逻辑运算符类

class Not(UnaryLogicOperator):
    def __init__(self, a):
        super().__init__(a)
        self.operator_name = "not"

class And(MultiLogicOperator):
    def __init__(self, *operands):
        super().__init__(*operands)
        self.operator_name = "and"

class Or(MultiLogicOperator):
    def __init__(self, *operands):
        super().__init__(*operands)
        self.operator_name = "or"

class Xor(BinaryLogicOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "xor"

# endregion

# region 条件运算符类

class Eq(BinaryConditionOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "eq"

class Ne(BinaryConditionOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "ne"

class Lt(BinaryConditionOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "lt"

class Gt(BinaryConditionOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "gt"

class Le(BinaryConditionOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "le"

class Ge(BinaryConditionOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "ge"

# endregion

# region 特殊条件运算符类

class ObjectMatch(SpecialConditionOperator):
    def __init__(self, pattern:dict):
        self.pattern = pattern
        self.operator_name = "object_match"
    def to_node(self) -> dict[str, Any]:
        return {**super().to_node(), 'pattern': self.pattern}

class ArrayInclude(SpecialConditionOperator):
    def __init__(self, path:str, contents:list):
        self.path = path
        self.contents = contents
        self.operator_name = "array_include"
    def to_node(self) -> dict[str, Any]:
        return {**super().to_node(), 'path': self.path, 'contents': self.contents}

# endregion