from meshops.services.weather import WeatherService

weather = WeatherService()

print(
    weather.current(
        38.573056,
        -121.428582,
    )
)
