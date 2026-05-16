from dataclasses import dataclass


@dataclass
class Account:
    available_cents: int
    balance_cents: int
    pending_cents: int


def account_balance(account: Account) -> int:
    return account.amount_cents

