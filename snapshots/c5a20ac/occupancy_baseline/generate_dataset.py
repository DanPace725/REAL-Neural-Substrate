from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

OUTPUT_PATH = Path(__file__).resolve().parent / 'data' / 'occupancy_synth_v1.csv'
ROW_INTERVAL_MINUTES = 15
DAYS = 14


@dataclass(frozen=True)
class OccupancyRow:
    row_id: int
    day_index: int
    minute_of_day: int
    temperature: float
    humidity: float
    light: float
    co2: float
    humidity_ratio: float
    occupancy: int



def _is_weekend(day_index: int) -> bool:
    return day_index % 7 in (5, 6)



def _scheduled_occupancy(day_index: int, minute_of_day: int) -> int:
    hour = minute_of_day / 60.0
    weekend = _is_weekend(day_index)
    if weekend:
        return 1 if 10.0 <= hour < 13.0 else 0
    if 8.0 <= hour < 12.0:
        return 1
    if 13.0 <= hour < 17.5:
        return 1
    return 0



def _daylight_profile(minute_of_day: int) -> float:
    hour = minute_of_day / 60.0
    if hour < 6.0 or hour > 20.0:
        return 0.05
    phase = (hour - 6.0) / 14.0
    return max(0.05, math.sin(math.pi * phase))



def _humidity_ratio(temperature_c: float, humidity_pct: float) -> float:
    return 0.00015 * humidity_pct + 0.00008 * temperature_c



def generate_rows(*, seed: int = 42, days: int = DAYS) -> List[OccupancyRow]:
    rng = random.Random(seed)
    rows: List[OccupancyRow] = []
    row_id = 0
    prev_co2 = 415.0

    for day_index in range(days):
        daily_temp_offset = rng.uniform(-0.9, 1.2)
        daily_humidity_offset = rng.uniform(-4.0, 4.0)
        for minute_of_day in range(0, 24 * 60, ROW_INTERVAL_MINUTES):
            row_id += 1
            occupancy = _scheduled_occupancy(day_index, minute_of_day)
            daylight = _daylight_profile(minute_of_day)
            hour = minute_of_day / 60.0

            if occupancy == 1 and rng.random() < 0.07:
                occupancy = 0
            elif occupancy == 0 and rng.random() < 0.03 and ((7.0 <= hour < 8.0) or (17.5 <= hour < 19.0)):
                occupancy = 1

            cleaning_event = 1 if (occupancy == 0 and rng.random() < 0.05 and 18.0 <= hour <= 21.0) else 0
            meeting_spike = 1 if (occupancy == 1 and rng.random() < 0.12) else 0
            auto_light = 1 if (daylight > 0.45 and rng.random() < 0.18) else 0

            outdoor_temp = 19.0 + 4.5 * daylight + daily_temp_offset
            temperature = outdoor_temp + 1.0 * occupancy + 0.6 * meeting_spike + 0.3 * cleaning_event + rng.uniform(-0.65, 0.65)

            humidity = 34.0 + 9.0 * (1.0 - daylight) + daily_humidity_offset - 1.7 * occupancy
            humidity += rng.uniform(-2.8, 2.8)
            humidity = max(22.0, min(58.0, humidity))

            base_light = 35.0 + 360.0 * daylight
            task_light = 135.0 * occupancy + 155.0 * cleaning_event + 120.0 * auto_light
            light = base_light + task_light + rng.uniform(-42.0, 42.0)
            light = max(0.0, light)

            target_co2 = 420.0 + 190.0 * occupancy + 95.0 * meeting_spike + 35.0 * cleaning_event
            prev_co2 = 0.88 * prev_co2 + 0.12 * target_co2 + rng.uniform(-11.0, 11.0)
            co2 = max(380.0, prev_co2)

            humidity_ratio = _humidity_ratio(temperature, humidity)
            humidity_ratio += 0.00002 * occupancy + rng.uniform(-0.00002, 0.00002)

            rows.append(
                OccupancyRow(
                    row_id=row_id,
                    day_index=day_index,
                    minute_of_day=minute_of_day,
                    temperature=round(temperature, 3),
                    humidity=round(humidity, 3),
                    light=round(light, 3),
                    co2=round(co2, 3),
                    humidity_ratio=round(humidity_ratio, 6),
                    occupancy=occupancy,
                )
            )
    return rows



def write_rows(rows: Iterable[OccupancyRow], output_path: str | Path = OUTPUT_PATH) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                'row_id',
                'day_index',
                'minute_of_day',
                'temperature',
                'humidity',
                'light',
                'co2',
                'humidity_ratio',
                'occupancy',
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
    return destination



def main() -> None:
    write_rows(generate_rows())
    print(f'Wrote benchmark dataset to {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
