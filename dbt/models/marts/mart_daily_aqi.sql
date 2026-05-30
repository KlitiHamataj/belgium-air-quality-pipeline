/*
    Mart: Daily Air Quality Index per station.

    Calculates Belgium's official BelAQI index (1-10 scale) based on
    daily average concentrations of PM2.5, PM10, NO2, and max 8-hour O3.
    The overall index is the worst (highest) of the individual pollutant indices.

    BelAQI scale:
        1-2: Very Good    3-4: Good       5-6: Moderate
        7-8: Poor         9-10: Very Poor / Horrible
*/

with hourly_data as (
    select * from {{ ref('int_air_quality_weather') }}
),

-- Pivot: one row per station per day, with avg for each pollutant
daily_station as (
    select
        station_id,
        station_label,
        station_lat,
        station_lon,
        data_source,
        cast(measured_at as date) as measurement_date,

        -- Daily averages per pollutant
        avg(case when pollutant = 'PM2.5' then measurement_value end) as avg_pm25,
        avg(case when pollutant = 'PM10' then measurement_value end) as avg_pm10,
        avg(case when pollutant = 'NO2' then measurement_value end) as avg_no2,
        -- O3 uses max daily 8-hour average (simplified: daily avg here)
        avg(case when pollutant = 'O3' then measurement_value end) as avg_o3,

        -- Weather context (daily averages)
        avg(temperature_2m) as avg_temperature,
        avg(relative_humidity_2m) as avg_humidity,
        avg(wind_speed_10m) as avg_wind_speed,
        avg(boundary_layer_height) as avg_boundary_layer,
        sum(precipitation) as total_precipitation,

        count(*) as measurement_count

    from hourly_data
    group by 1, 2, 3, 4, 5, 6
),

-- Calculate BelAQI sub-indices for each pollutant
with_indices as (
    select
        *,

        -- PM2.5 index (1-10)
        case
            when avg_pm25 is null then null
            when avg_pm25 <= 5 then 1
            when avg_pm25 <= 10 then 2
            when avg_pm25 <= 15 then 3
            when avg_pm25 <= 25 then 4
            when avg_pm25 <= 35 then 5
            when avg_pm25 <= 45 then 6
            when avg_pm25 <= 55 then 7
            when avg_pm25 <= 65 then 8
            when avg_pm25 <= 75 then 9
            else 10
        end as belaqi_pm25,

        -- PM10 index
        case
            when avg_pm10 is null then null
            when avg_pm10 <= 10 then 1
            when avg_pm10 <= 20 then 2
            when avg_pm10 <= 30 then 3
            when avg_pm10 <= 40 then 4
            when avg_pm10 <= 50 then 5
            when avg_pm10 <= 60 then 6
            when avg_pm10 <= 70 then 7
            when avg_pm10 <= 80 then 8
            when avg_pm10 <= 100 then 9
            else 10
        end as belaqi_pm10,

        -- NO2 index
        case
            when avg_no2 is null then null
            when avg_no2 <= 10 then 1
            when avg_no2 <= 20 then 2
            when avg_no2 <= 30 then 3
            when avg_no2 <= 50 then 4
            when avg_no2 <= 70 then 5
            when avg_no2 <= 100 then 6
            when avg_no2 <= 150 then 7
            when avg_no2 <= 200 then 8
            when avg_no2 <= 400 then 9
            else 10
        end as belaqi_no2,

        -- O3 index
        case
            when avg_o3 is null then null
            when avg_o3 <= 20 then 1
            when avg_o3 <= 40 then 2
            when avg_o3 <= 60 then 3
            when avg_o3 <= 80 then 4
            when avg_o3 <= 100 then 5
            when avg_o3 <= 140 then 6
            when avg_o3 <= 180 then 7
            when avg_o3 <= 240 then 8
            when avg_o3 <= 380 then 9
            else 10
        end as belaqi_o3

    from daily_station
)

select
    station_id,
    station_label,
    station_lat,
    station_lon,
    data_source,
    measurement_date,
    avg_pm25,
    avg_pm10,
    avg_no2,
    avg_o3,
    belaqi_pm25,
    belaqi_pm10,
    belaqi_no2,
    belaqi_o3,

    -- Overall BelAQI = worst sub-index
    greatest(
        coalesce(belaqi_pm25, 0),
        coalesce(belaqi_pm10, 0),
        coalesce(belaqi_no2, 0),
        coalesce(belaqi_o3, 0)
    ) as belaqi_overall,

    case greatest(
        coalesce(belaqi_pm25, 0),
        coalesce(belaqi_pm10, 0),
        coalesce(belaqi_no2, 0),
        coalesce(belaqi_o3, 0)
    )
        when 1 then 'Very Good'
        when 2 then 'Very Good'
        when 3 then 'Good'
        when 4 then 'Good'
        when 5 then 'Moderate'
        when 6 then 'Moderate'
        when 7 then 'Poor'
        when 8 then 'Poor'
        when 9 then 'Very Poor'
        when 10 then 'Horrible'
        else 'Unknown'
    end as belaqi_label,

    -- Weather context
    avg_temperature,
    avg_humidity,
    avg_wind_speed,
    avg_boundary_layer,
    total_precipitation,
    measurement_count

from with_indices
