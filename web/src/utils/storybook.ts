import moment from 'moment'
import { isNoonInPST } from 'utils/date'

const getPastValues = () => {
  const _observedValues = []
  const _pastForecastValues = []
  const _forecastSummaries = []
  const _pastModelValues = []
  const _modelSummaries = []
  const _pastHighResModelValues = []
  const _highResModelSummaries = []
  const _pastRegionalModelValues = []
  const _regionalModelSummaries = []

  const days = 3
  const first = moment()
    .utc()
    .set({ minute: 0, second: 0 })
    .subtract(days, 'days')
  const last = moment(first).add(days - 1, 'days')

  while (last.diff(first, 'days') >= 0) {
    for (let length = 0; length < 24; length++) {
      const sineWeight = 7
      const temp = 20 + Math.sin(length) * sineWeight
      const rh = 20 - Math.sin(length) * sineWeight
      const wind_speed = 20 + Math.sin(length) * sineWeight
      const wind_direction = Math.floor(Math.random() * 360)
      const barometric_pressure = 10 + Math.sin(length) * sineWeight
      const precip = Math.random()
      const datetime = moment(first)
        .add(length, 'hours')
        .utc()
        .format()

      // every hour
      _observedValues.push({
        datetime,
        temperature: Math.random() <= 0.8 ? temp : null,
        relative_humidity: rh,
        wind_speed,
        wind_direction,
        barometric_pressure,
        precipitation: precip,
        ffmc: null,
        isi: null,
        fwi: null
      })
      _pastHighResModelValues.push({
        datetime,
        temperature: temp + (Math.random() - 0.5) * 6,
        bias_adjusted_temperature: temp + (Math.random() - 0.5) * 6 - 2,
        relative_humidity: rh + (Math.random() - 0.5) * 6,
        bias_adjusted_relative_humidity: rh + (Math.random() - 0.5) * 6 - 2,
        delta_precipitation: precip,
        wind_speed: wind_speed + (Math.random() - 0.5) * 6,
        wind_direction: wind_direction + (((Math.random() - 0.5) * 6) % 360)
      })
      _highResModelSummaries.push({
        datetime,
        tmp_tgl_2_5th: temp - 3,
        tmp_tgl_2_median: temp,
        tmp_tgl_2_90th: temp + 3,
        rh_tgl_2_5th: rh - 3,
        rh_tgl_2_median: rh,
        rh_tgl_2_90th: rh + 3
      })
      _pastRegionalModelValues.push({
        datetime,
        temperature: temp + (Math.random() - 0.7) * 7,
        bias_adjusted_temperature: temp + (Math.random() - 0.7) * 7 - 2,
        relative_humidity: rh + (Math.random() - 0.7) * 7,
        bias_adjusted_relative_humidity: rh - (Math.random() - 0.7) * 7 - 2,
        delta_precipitation: precip
      })
      _regionalModelSummaries.push({
        datetime,
        tmp_tgl_2_5th: temp - 4 - Math.random(),
        tmp_tgl_2_median: temp,
        tmp_tgl_2_90th: temp + 4 - Math.random() * 3,
        rh_tgl_2_5th: rh - 4 - Math.random(),
        rh_tgl_2_median: rh,
        rh_tgl_2_90th: rh + 4 + Math.random() * 3
      })

      if (isNoonInPST(datetime)) {
        _pastForecastValues.push({
          datetime,
          temperature: temp + (Math.random() - 0.5) * 8,
          relative_humidity: rh + (Math.random() - 0.5) * 8,
          total_precipitation: 24 * precip + Math.random() * 4
        })
        _forecastSummaries.push({
          datetime,
          tmp_min: temp + (Math.random() - 1) * 2 - 4,
          tmp_max: temp + Math.random() * 2 + 4,
          rh_min: rh + (Math.random() - 1) * 2 - 4,
          rh_max: rh + Math.random() * 2 + 4
        })
      }

      // every 3 hour
      if (length % 3 === 0) {
        _pastModelValues.push({
          datetime,
          temperature: temp + (Math.random() - 0.5) * 8,
          bias_adjusted_temperature: temp + (Math.random() - 0.5) * 8 - 2,
          relative_humidity: rh + (Math.random() - 0.5) * 8,
          bias_adjusted_relative_humidity: rh + (Math.random() - 0.5) * 8 - 2,
          delta_precipitation: precip
        })
        _modelSummaries.push({
          datetime,
          tmp_tgl_2_5th: temp - 4,
          tmp_tgl_2_median: temp,
          tmp_tgl_2_90th: temp + 4,
          rh_tgl_2_5th: rh - 4,
          rh_tgl_2_median: rh,
          rh_tgl_2_90th: rh + 4
        })
      }
    }

    first.add(1, 'days')
  }

  return {
    observedValues: _observedValues,
    pastForecastValues: _pastForecastValues,
    forecastSummaries: _forecastSummaries,
    pastModelValues: _pastModelValues,
    modelSummaries: _modelSummaries,
    pastHighResModelValues: _pastHighResModelValues,
    highResModelSummaries: _highResModelSummaries,
    pastRegionalModelValues: _pastRegionalModelValues,
    regionalModelSummaries: _regionalModelSummaries
  }
}

const getFutureValues = () => {
  const _modelValues = []
  const _highResModelValues = []
  const _regionalModelValues = []
  const _forecastValues = []

  // GDPS goes out 10 days.
  const days = 10
  const first = moment()
    .utc()
    .set({ minute: 0, second: 0 })
  const day = moment()
    .utc()
    .set({ minute: 0, second: 0 })
  const last = moment(day).add(days, 'days')

  while (last.diff(day, 'days') >= 0) {
    for (let length = 0; length < 24; length++) {
      const sineWeight = 7
      const temp = 20 + Math.sin(length) * sineWeight
      const rh = 20 - Math.sin(length) * sineWeight
      const dew_point = 20 + Math.sin(length) * sineWeight
      const wind_speed = 20 + Math.sin(length) * sineWeight
      const wind_direction = Math.floor(Math.random() * 360)
      const precip = Math.random()
      const datetime = moment(day)
        .add(length, 'hours')
        .utc()
        .format()

      // HRDPS only goes out 48 hours
      if (day.diff(first, 'days') <= 2) {
        // every hour
        _highResModelValues.push({
          datetime,
          temperature: temp + (Math.random() - 0.5) * 6,
          bias_adjusted_temperature: temp + (Math.random() - 0.5) * 6 - 2,
          relative_humidity: rh + (Math.random() - 0.5) * 6,
          bias_adjusted_relative_humidity: rh + (Math.random() - 0.5) * 6 - 2,
          delta_precipitation: precip * Math.random() * 7,
          wind_speed: wind_speed + (Math.random() - 0.5) * 4,
          wind_direction: wind_direction + (((Math.random() - 0.5) * 90) % 360)
        })
      }

      // REGIONAL model goes out 84 hours.
      if (day.diff(first, 'days') <= 4) {
        // every hour
        _regionalModelValues.push({
          datetime,
          temperature: temp + (Math.random() - 1.4) * 9 + 1.5,
          bias_adjusted_temperature: temp + (Math.random() - 1.4) * 9 - 4,
          relative_humidity: rh + (Math.random() - 1.4) * 9,
          bias_adjusted_relative_humidity: rh - (Math.random() - 1.4) * 7 - 4,
          delta_precipitation: precip * Math.random() * 8,
          wind_speed: wind_speed + (Math.random() - 0.5) * 6,
          wind_direction: wind_direction + (((Math.random() - 0.5) * 90) % 360)
        })
      }

      // GLOBAL model every 3 hour and PST noon
      if (length % 3 === 0 || isNoonInPST(datetime)) {
        _modelValues.push({
          datetime,
          temperature: temp + (Math.random() - 0.5) * 8,
          bias_adjusted_temperature: temp + (Math.random() - 0.5) * 8 - 2,
          dew_point,
          relative_humidity: rh + (Math.random() - 0.5) * 8,
          bias_adjusted_relative_humidity: rh + (Math.random() - 0.5) * 8 - 5,
          wind_speed,
          wind_direction,
          delta_precipitation: precip * Math.random() * 5
        })
      }

      // every PST noon, 3 days out
      if (day.diff(first, 'days') <= 3) {
        if (isNoonInPST(datetime)) {
          _forecastValues.push({
            datetime,
            temperature: temp + (Math.random() - 0.5) * 8,
            relative_humidity: rh + (Math.random() - 0.5) * 8,
            total_precipitation: 24 * precip + Math.random() * 4,
            wind_speed: wind_speed + (Math.random() - 0.5) * 10,
            wind_direction: wind_direction + (((Math.random() - 0.5) * 45) % 360)
          })
        }
      }
    }

    day.add(1, 'days')
  }

  return {
    modelValues: _modelValues,
    highResModelValues: _highResModelValues,
    regionalModelValues: _regionalModelValues,
    forecastValues: _forecastValues
  }
}

export const {
  forecastValues,
  modelValues,
  highResModelValues,
  regionalModelValues
} = getFutureValues()

export const {
  observedValues,
  pastForecastValues,
  forecastSummaries,
  pastModelValues,
  modelSummaries,
  pastHighResModelValues,
  highResModelSummaries,
  pastRegionalModelValues,
  regionalModelSummaries
} = getPastValues()
