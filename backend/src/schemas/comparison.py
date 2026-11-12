from pydantic import BaseModel,Field,model_validator
from src.constants.enums import INPUTS,OUTPUTS
class ComparisonInput(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    before_benchmark_id:int
    after_benchmark_id:int
    inputs:list[str]=Field(default_factory=lambda:list(INPUTS),min_length=1,max_length=2)
    outputs:list[str]=Field(default_factory=lambda:list(OUTPUTS),min_length=1,max_length=2)
    @model_validator(mode='after')
    def valid(self):
        if self.before_benchmark_id==self.after_benchmark_id:raise ValueError('跨期比较需要两个不同的同期参照集')
        if len(set(self.inputs))!=len(self.inputs) or len(set(self.outputs))!=len(self.outputs) or any(f not in INPUTS for f in self.inputs) or any(f not in OUTPUTS for f in self.outputs):raise ValueError('投入产出字段非法或重复')
        return self
