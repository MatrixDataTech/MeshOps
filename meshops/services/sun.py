"""Calculate local sunrise and sunset without an Internet dependency."""

from datetime import date, datetime, time, timedelta, timezone
from math import acos, asin, cos, degrees, radians, sin, tan
from zoneinfo import ZoneInfo

from meshops.models.sun import SunTimes


class SunService:
    """Calculate apparent sunrise and sunset from location and date.

    The calculation uses the NOAA solar-equation approach with the standard
    90.833-degree apparent-sunrise zenith correction.
    """

    APPARENT_SUNRISE_ZENITH = 90.833

    def __init__(self, timezone_name: str):
        self.timezone = ZoneInfo(timezone_name)

    def for_location(
        self,
        latitude: float,
        longitude: float,
        day: date | None = None,
    ) -> SunTimes | None:
        """Return local sun times for a location, or None where no event occurs."""

        day = day or datetime.now(self.timezone).date()
        julian_century = self._julian_century(day)
        equation_of_time = self._equation_of_time(julian_century)
        declination = self._solar_declination(julian_century)
        hour_angle = self._sunrise_hour_angle(latitude, declination)

        if hour_angle is None:
            return None

        solar_noon = 720 - (4 * longitude) - equation_of_time
        sunrise_minutes = solar_noon - (4 * hour_angle)
        sunset_minutes = solar_noon + (4 * hour_angle)

        return SunTimes(
            sunrise=self._local_time(day, sunrise_minutes),
            sunset=self._local_time(day, sunset_minutes),
        )

    @staticmethod
    def _julian_century(day: date) -> float:
        julian_day = day.toordinal() + 1721424.5
        return (julian_day - 2451545.0) / 36525.0

    @staticmethod
    def _equation_of_time(julian_century: float) -> float:
        epsilon = SunService._obliquity_correction(julian_century)
        longitude = SunService._geometric_mean_longitude(julian_century)
        eccentricity = SunService._eccentricity(julian_century)
        anomaly = SunService._geometric_mean_anomaly(julian_century)
        y = tan(radians(epsilon) / 2) ** 2

        return 4 * degrees(
            y * sin(2 * radians(longitude))
            - 2 * eccentricity * sin(radians(anomaly))
            + 4 * eccentricity * y * sin(radians(anomaly)) * cos(2 * radians(longitude))
            - 0.5 * y * y * sin(4 * radians(longitude))
            - 1.25 * eccentricity * eccentricity * sin(2 * radians(anomaly))
        )

    @staticmethod
    def _solar_declination(julian_century: float) -> float:
        obliquity = SunService._obliquity_correction(julian_century)
        longitude = SunService._sun_apparent_longitude(julian_century)
        return degrees(asin(sin(radians(obliquity)) * sin(radians(longitude))))

    @staticmethod
    def _sunrise_hour_angle(latitude: float, declination: float) -> float | None:
        cosine = (
            cos(radians(SunService.APPARENT_SUNRISE_ZENITH))
            / (cos(radians(latitude)) * cos(radians(declination)))
            - tan(radians(latitude)) * tan(radians(declination))
        )

        if cosine < -1 or cosine > 1:
            return None

        return degrees(acos(cosine))

    @staticmethod
    def _geometric_mean_longitude(julian_century: float) -> float:
        return (280.46646 + julian_century * (36000.76983 + 0.0003032 * julian_century)) % 360

    @staticmethod
    def _geometric_mean_anomaly(julian_century: float) -> float:
        return 357.52911 + julian_century * (35999.05029 - 0.0001537 * julian_century)

    @staticmethod
    def _eccentricity(julian_century: float) -> float:
        return 0.016708634 - julian_century * (0.000042037 + 0.0000001267 * julian_century)

    @staticmethod
    def _sun_equation_of_center(julian_century: float) -> float:
        anomaly = SunService._geometric_mean_anomaly(julian_century)
        return (
            sin(radians(anomaly)) * (1.914602 - julian_century * (0.004817 + 0.000014 * julian_century))
            + sin(2 * radians(anomaly)) * (0.019993 - 0.000101 * julian_century)
            + sin(3 * radians(anomaly)) * 0.000289
        )

    @staticmethod
    def _sun_apparent_longitude(julian_century: float) -> float:
        true_longitude = (
            SunService._geometric_mean_longitude(julian_century)
            + SunService._sun_equation_of_center(julian_century)
        )
        omega = 125.04 - 1934.136 * julian_century
        return true_longitude - 0.00569 - 0.00478 * sin(radians(omega))

    @staticmethod
    def _obliquity_correction(julian_century: float) -> float:
        mean_obliquity = 23 + (
            26 + ((21.448 - julian_century * (46.815 + julian_century * (0.00059 - julian_century * 0.001813))) / 60)
        ) / 60
        omega = 125.04 - 1934.136 * julian_century
        return mean_obliquity + 0.00256 * cos(radians(omega))

    def _local_time(self, day: date, minutes_from_utc_midnight: float) -> datetime:
        utc_time = datetime.combine(day, time(), tzinfo=timezone.utc)
        return (utc_time + timedelta(minutes=minutes_from_utc_midnight)).astimezone(self.timezone)
