from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# region 所有抽象运算符类

class Operator(ABC):
    operator_type:str
    operator_name:str

class LogicOperator(Operator):
    operator_type:str = "logic"

class UnaryLogicOperator(LogicOperator):
    def __init__(self, a:Operator):
        self.a = a

class BinaryLogicOperator(LogicOperator):
    def __init__(self, a:Operator, b:Operator):
        self.a = a
        self.b = b

class ConditionOperator(Operator):
    operator_type:str = "condition"

class UnaryConditionOperator(ConditionOperator):
    def __init__(self, a:str):
        self.a = a

class BinaryConditionOperator(ConditionOperator):
    def __init__(self, a:str, b:Any):
        self.a = a
        self.b = b

class SpecialConditionOperator(ConditionOperator):
    operator_type:str = "special_condition"
    pass

# endregion

# region 空运算符
class VoidOperator(Operator):
    operator_type:str = "void"
    def __init__(self):
        self.operator_name = "void"

# region 逻辑运算符类

class Not(UnaryLogicOperator):
    def __init__(self, a):
        super().__init__(a)
        self.operator_name = "not"

class And(BinaryLogicOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
        self.operator_name = "and"

class Or(BinaryLogicOperator):
    def __init__(self, a, b):
        super().__init__(a, b)
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

class ArrayInclude(SpecialConditionOperator):
    def __init__(self, path:str, contents:list):
        self.path = path
        self.contents = contents
        self.operator_name = "array_include"

# endregion