from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrainingDataConfig:
    data_path: Path
    validation_fraction: float | None = None

    def __post_init__(self) -> None:
        if self.data_path.is_file() and self.validation_fraction is None:
            raise ValueError(
                "If data_path is a file, validation_fraction must be set to split validation data."
            )
        if not self.data_path.exists():
            raise FileNotFoundError(f"data_path does not exist: {self.data_path}")
