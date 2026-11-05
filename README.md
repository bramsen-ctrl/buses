# in progress interactive map of madison buses

Open `index.html` through a local web server, for example:

```bash
python3 -m http.server 8000
```

Then visit `http://localhost:8000/index.html`. The map shows route shapes and scheduled stop departures from the Madison Metro GTFS feed. The bundled feed is valid August 16 through December 5, 2026; schedules are not live arrival predictions.

To refresh the bundled data, download the current [Madison Metro GTFS feed](https://transitdata.cityofmadison.com/GTFS/mmt_gtfs.zip) and run:

```bash
python3 build_gtfs_data.py path/to/mmt_gtfs.zip
```

Data provided under license granted by City of Madison, WI, Metro Transit. See the [data terms](https://transitdata.cityofmadison.com/MetroTransitDataTermsOfUse.pdf).
