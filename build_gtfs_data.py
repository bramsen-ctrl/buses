"""Build a compact browser data file from Madison Metro's GTFS ZIP."""

import argparse
import csv
import gzip
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path


def rows(archive, filename):
    with archive.open(filename) as source:
        return list(csv.DictReader(io.TextIOWrapper(source, encoding="utf-8-sig")))


def gtfs_time_seconds(value):
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def build(source, destination):
    with zipfile.ZipFile(source) as archive:
        feed_info = rows(archive, "feed_info.txt")[0]
        agency = rows(archive, "agency.txt")[0]
        raw_routes = rows(archive, "routes.txt")
        raw_routes.sort(key=lambda route: int(route.get("route_sort_order") or 0))
        route_indices = {route["route_id"]: index for index, route in enumerate(raw_routes)}
        routes = [
            [
                route["route_id"],
                route.get("route_short_name", ""),
                route.get("route_long_name", ""),
            ]
            for route in raw_routes
        ]

        calendars = {row["service_id"]: row for row in rows(archive, "calendar.txt")}
        raw_exceptions = rows(archive, "calendar_dates.txt")
        service_ids = set(calendars)
        service_ids.update(row["service_id"] for row in raw_exceptions)
        service_ids = sorted(service_ids)
        service_indices = {service_id: index for index, service_id in enumerate(service_ids)}
        services = []
        for service_id in service_ids:
            calendar = calendars.get(service_id, {})
            days = "".join(calendar.get(day, "0") for day in (
                "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
            ))
            services.append([
                service_id,
                days,
                calendar.get("start_date", ""),
                calendar.get("end_date", ""),
            ])
        exceptions = sorted([
            service_indices[row["service_id"]],
            row["date"],
            int(row["exception_type"]),
        ] for row in raw_exceptions)

        headsigns = []
        headsign_indices = {}

        def headsign_index(value):
            value = value.strip()
            if value not in headsign_indices:
                headsign_indices[value] = len(headsigns)
                headsigns.append(value)
            return headsign_indices[value]

        trips = {}
        shapes_by_id = defaultdict(set)
        for trip in rows(archive, "trips.txt"):
            route_index = route_indices.get(trip["route_id"])
            service_index = service_indices.get(trip["service_id"])
            if route_index is None or service_index is None:
                continue
            shape_id = trip.get("shape_id", "")
            trips[trip["trip_id"]] = (
                route_index,
                service_index,
                headsign_index(trip.get("trip_headsign", "")),
                shape_id,
            )
            if shape_id:
                shapes_by_id[shape_id].add(route_index)

        stops_by_id = {}
        for stop in rows(archive, "stops.txt"):
            try:
                latitude = float(stop["stop_lat"])
                longitude = float(stop["stop_lon"])
            except (KeyError, ValueError):
                continue
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                continue
            stops_by_id[stop["stop_id"]] = [
                stop["stop_id"],
                stop.get("stop_code", ""),
                stop.get("stop_name", ""),
                round(latitude, 5),
                round(longitude, 5),
                [],
            ]

        with archive.open("stop_times.txt") as source_file:
            stop_times = csv.DictReader(io.TextIOWrapper(source_file, encoding="utf-8-sig"))
            for stop_time in stop_times:
                trip = trips.get(stop_time["trip_id"])
                stop = stops_by_id.get(stop_time["stop_id"])
                scheduled_time = stop_time.get("departure_time") or stop_time.get("arrival_time")
                if trip is None or stop is None or not scheduled_time:
                    continue
                route_index, service_index, trip_headsign, _ = trip
                sign = stop_time.get("stop_headsign", "").strip()
                sign_index = headsign_index(sign) if sign else trip_headsign
                stop[5].append([
                    route_index,
                    service_index,
                    gtfs_time_seconds(scheduled_time),
                    sign_index,
                ])

        for stop in stops_by_id.values():
            stop[5].sort(key=lambda event: (event[2], event[0], event[3]))

        shape_points = defaultdict(list)
        with archive.open("shapes.txt") as source_file:
            shape_rows = csv.DictReader(io.TextIOWrapper(source_file, encoding="utf-8-sig"))
            for point in shape_rows:
                if point["shape_id"] not in shapes_by_id:
                    continue
                shape_points[point["shape_id"]].append((
                    int(point["shape_pt_sequence"]),
                    round(float(point["shape_pt_lat"]), 5),
                    round(float(point["shape_pt_lon"]), 5),
                ))

        shapes = []
        for shape_id, route_set in shapes_by_id.items():
            points = sorted(shape_points.get(shape_id, []))
            if len(points) < 2:
                continue
            coordinates = [[latitude, longitude] for _, latitude, longitude in points]
            shapes.extend([route_index, coordinates] for route_index in sorted(route_set))

        data = {
            "feed": [
                feed_info.get("feed_publisher_name", "Metro Transit-City of Madison"),
                feed_info.get("feed_start_date", ""),
                feed_info.get("feed_end_date", ""),
                feed_info.get("feed_version", ""),
                agency.get("agency_timezone", "America/Chicago"),
            ],
            "routes": routes,
            "services": services,
            "exceptions": exceptions,
            "headsigns": headsigns,
            "shapes": shapes,
            "stops": list(stops_by_id.values()),
        }

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(destination, "wt", encoding="utf-8", compresslevel=9) as output:
        json.dump(data, output, ensure_ascii=False, separators=(",", ":"))

    stop_time_count = sum(len(stop[5]) for stop in data["stops"])
    print(
        f"Wrote {destination}: {len(routes)} routes, {len(shapes)} route shapes, "
        f"{len(stops_by_id)} stops, {stop_time_count} scheduled stop times; "
        f"feed valid {data['feed'][1]}–{data['feed'][2]}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed", help="Madison Metro GTFS ZIP file")
    parser.add_argument("--output", default="data/madison-metro.json.gz")
    arguments = parser.parse_args()
    build(arguments.feed, arguments.output)


if __name__ == "__main__":
    main()