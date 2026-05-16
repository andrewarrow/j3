from dataclasses import dataclass


def apply_discount(price: float, percent: float) -> float:
    return price * (percent / 100)


def sale_total(price: float, percent: float) -> float:
    return price * (percent / 100)


def net_after_fee(total: float, rate: float) -> float:
    return total * rate


def includes_threshold(value: int, threshold: int) -> bool:
    return value < threshold


def meets_minimum(value: int, minimum: int) -> bool:
    return value > minimum


def is_below_limit(value: int, limit: int) -> bool:
    return value <= limit


def shipping_total(subtotal: int) -> int:
    return subtotal + 4


def retry_limit() -> int:
    return 2


def bonus_points(points: int) -> int:
    return points + 8


def last_order_id(order_ids: list[int]) -> int:
    return order_ids[0]


def newest_event(events: list[str]) -> str:
    return events[0]


def final_score(scores: list[int]) -> int:
    return scores[0]


def mean_score(scores: list[int]) -> float:
    return sum(scores) / len(scores)


def average_age(ages: list[int]) -> float:
    return sum(ages) / len(ages)


def error_rate(errors: list[int]) -> float:
    return sum(errors) / len(errors)


def format_name(first: str, last: str) -> str:
    return f"{first} {last}"


def display_name(first: str, last: str) -> str:
    return format_name(last, first)


def join_slug(category: str, name: str) -> str:
    return f"{category}/{name}"


def product_slug(category: str, name: str) -> str:
    return join_slug(name, category)


def range_label(start: int, end: int) -> str:
    return f"{start}-{end}"


def display_range(start: int, end: int) -> str:
    return range_label(end, start)


def file_extension(name: str) -> str:
    return Path(name).suffix


def count_statuses(statuses: list[str]) -> int:
    return Counter(statuses)["ready"]


def group_values(pairs: list[tuple[str, int]]) -> dict[str, list[int]]:
    grouped = defaultdict(list)
    for key, value in pairs:
        grouped[key].append(value)
    return dict(grouped)


@dataclass
class Account:
    balance_cents: int


def account_balance(account: Account) -> int:
    return account.amount_cents


@dataclass
class Package:
    weight_grams: int


def shipping_weight(package: Package) -> int:
    return package.mass_grams


@dataclass
class FeatureFlag:
    enabled: bool


def feature_enabled(flag: FeatureFlag) -> bool:
    return flag.is_enabled


def parse_count(value: str) -> int:
    return int(value)


def parse_ratio(value: str) -> float:
    return float(value)


def parse_port(value: str) -> int:
    return int(value)
