"""Compatibility exports for expression-oriented generators."""

from .calls import (
    _add_keyword_arg_candidates,
    _call_signature_index,
    _swap_call_arg_candidates,
)
from .control_flow import (
    _guard_candidates,
    _modify_condition_candidates,
    _return_candidates,
    _wrap_try_except_candidates,
)
from .data_access import _attribute_candidates, _last_item_candidate, _subscript_key_candidates
from .literals import _compare_candidates, _literal_candidates
from .symbols import _rename_symbol_candidates

__all__ = [
    "_attribute_candidates",
    "_add_keyword_arg_candidates",
    "_call_signature_index",
    "_compare_candidates",
    "_guard_candidates",
    "_last_item_candidate",
    "_literal_candidates",
    "_modify_condition_candidates",
    "_rename_symbol_candidates",
    "_return_candidates",
    "_subscript_key_candidates",
    "_swap_call_arg_candidates",
    "_wrap_try_except_candidates",
]
