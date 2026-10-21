# E. coli with rainfall and streamflow: negative result

## Conclusion

**Regional rainfall and streamflow did not improve E. coli forecasts. The v2 model stays.** The weather model was worse than v2 in both development years, so under the rule committed beforehand (`ecoli_weather.py` docstring, commit `87bc919`) no v3 candidate was created. Nothing about the frozen models or the prospective protocol changes.

## What was tested

- **Data:** E. coli forecasts with sample dates before January 1, 2025 only. The 2025–April 2026 test period was not used.
- **Weather inputs (known at issue time):** regional mean rainfall from four NOAA stations (Sea-Tac, Paine Field, Sand Point, Boeing Field) summed over 1, 3, 7, 14 and 30 days; days since 5 mm of rain; Issaquah Creek (USGS 12121600) daily flow, 7-day mean flow, and flow relative to its 30-day median. All end the day before the forecast is issued, a week before sampling.
- **Oracle diagnostic:** the same plus rain on the sample day and the three days before. This is unknown when a forecast is issued; it shows the most a perfect rain forecast could add.
- **Model:** the v2 random forest settings, unchanged. Each year is scored after training on data ending ten days before it.

## Results

Mean absolute error in log(1 + E. coli); lower is better.

| Year | Test samples | Sites | v2 | v2 + weather | v2 + weather + oracle rain |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023 | 229 | 28 | 1.542 | 1.658 | 1.658 |
| 2024 | 214 | 31 | 1.362 | 1.381 | 1.397 |

Site-bootstrap 95% intervals for the change in error versus v2 (positive means better):

| Year | Weather | Oracle |
| --- | --- | --- |
| 2023 | −0.156 to −0.075 | −0.162 to −0.072 |
| 2024 | −0.062 to +0.028 | −0.080 to +0.012 |

In 2023 the weather model is clearly worse; in 2024 it is no better.

## Why it did not help

Rank correlations across the 1,653 development forecasts:

| Input | With log E. coli | With what the site-seasonal baseline misses |
| --- | ---: | ---: |
| Rain on sample day and 3 days before (oracle) | −0.02 | +0.00 |
| Rain, 3 days before issue | −0.17 | −0.15 |
| Rain, 30 days before issue | −0.30 | −0.23 |
| Issaquah Creek flow at issue | −0.32 | −0.22 |

- **Storm rain shows no link.** Rain just before sampling, the usual driver of E. coli runoff spikes, is unrelated to these results. Two-thirds of samples had more than 1 mm of regional rain in that window, so this is not a lack of wet-day samples.
- **Wet periods mean lower E. coli.** Higher antecedent rain and flow go with lower values, which fits dilution in the wet season and higher counts in warm, low-flow months. The month and site-seasonal features already capture most of this, and the extra inputs mainly added noise to the forest.

## Limits

- Rain and flow are regional. The sites span Everett to Kent, and summer storms are often local. The export has no site coordinates, so per-site rain or the nearest gauge could not be used. A data-owner site registry with coordinates (request item 1) would allow that test.
- Archived NOAA and USGS values include later quality review; values available in real time are provisional.
- Daily data cannot tell whether same-day rain fell before or after sampling.
- This is two years of retrospective development, not a prospective result. It shows that this regional proxy is not worth adding. It does not show that weather is irrelevant to E. coli at these creeks.

## Reproduce

```sh
.venv/bin/python weather.py fetch      # optional: refresh data/external
.venv/bin/python ecoli_weather.py      # writes development.json; refuses post-2024 samples
```
