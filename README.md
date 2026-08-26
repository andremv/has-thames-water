# Thames Water for Home Assistant

A custom integration that pulls your water usage from the
[Thames Water My Account](https://myaccount.thameswater.co.uk) portal and
exposes it as sensors in Home Assistant.

It logs in to the My Account portal using the same Azure AD B2C sign-in flow
as the website, then reads the smart-meter usage API.

## Sensors

| Sensor | Unit | Description |
| --- | --- | --- |
| `sensor.water_meter_reading` | m³ | Cumulative meter reading (total-increasing) |
| `sensor.water_usage_latest_day` | L | Usage for the most recent day of data |
| `sensor.water_usage_latest_hour` | L | Usage for the most recent hourly reading |
| `sensor.water_usage_last_30_days` | L | Total over the last 30 days |
| `sensor.water_usage_daily_average` | L | Daily average over the period |
| `sensor.water_usage_billing_period` | L | Consumption for the current billing period |

Thames Water typically lags a couple of days behind, so the "latest"
sensors refer to the most recent data available rather than today.

Each sensor carries attributes with the meter serial number, premise address
and the time of the latest reading.

## Installation

Copy the `custom_components/thames_water` folder into your
`config/custom_components/` directory:

```sh
mkdir -p config/custom_components
cp -r custom_components/thames_water config/custom_components/
```

Restart Home Assistant, then add the integration from
**Settings → Devices & Services → Add Integration → Thames Water** and enter
your My Account email and password.

The data refreshes every 30 minutes.

## Notes

- This is an unofficial integration and relies on the My Account web portal,
  which Thames Water may change at any time.
- Your email and password are stored in Home Assistant's configuration entry
  (encrypted at rest in `.storage`).
