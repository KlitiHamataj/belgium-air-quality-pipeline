/*
    Mart: Station summary statistics.

    One row per station with aggregate stats across all available days.
    Useful for the dashboard's station comparison view and the API's
    station metadata endpoint.
*/

with daily as (
    select * from {{ ref('mart_daily_aqi') }}
),

station_stats as (
    select
        station_id,
        station_label,
        station_lat,
        station_lon,
        data_source,

        -- Date range
        min(measurement_date) as first_measurement,
        max(measurement_date) as last_measurement,
        count(distinct measurement_date) as days_with_data,

        -- Average pollutant levels
        round(avg(avg_pm25), 1) as mean_pm25,
        round(avg(avg_pm10), 1) as mean_pm10,
        round(avg(avg_no2), 1) as mean_no2,
        round(avg(avg_o3), 1) as mean_o3,

        -- Peak values
        round(max(avg_pm25), 1) as max_pm25,
        round(max(avg_pm10), 1) as max_pm10,
        round(max(avg_no2), 1) as max_no2,
        round(max(avg_o3), 1) as max_o3,

        -- BelAQI distribution
        round(avg(belaqi_overall), 1) as mean_belaqi,
        max(belaqi_overall) as worst_belaqi,
        count(case when belaqi_overall >= 7 then 1 end) as days_poor_or_worse,
        count(case when belaqi_overall <= 4 then 1 end) as days_good_or_better,

        -- Weather correlations (averages during measurements)
        round(avg(avg_temperature), 1) as mean_temperature,
        round(avg(avg_wind_speed), 1) as mean_wind_speed,
        round(avg(avg_boundary_layer), 0) as mean_boundary_layer,

        sum(measurement_count) as total_measurements

    from daily
    group by 1, 2, 3, 4, 5
)

select
    *,
    -- Percentage of days with poor+ air quality
    round(
        100.0 * days_poor_or_worse / nullif(days_with_data, 0), 1
    ) as pct_days_poor
from station_stats
