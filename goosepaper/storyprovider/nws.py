import datetime
import re
import requests
from typing import List

from .storyprovider import StoryProvider
from ..story import Story


class NWSStoryProvider(StoryProvider):
    def __init__(
        self,
        lat: float,
        lon: float,
        F: bool,
        products: List[str] = []
    ) -> None:
        self.units = 'us' if F else 'si'
        self.products = products

        pointsResp = requests.get(
                f"https://api.weather.gov/points/{lat},{lon}"
        ).json()
        if pointsResp.get('properties'):
            self.grid_x = pointsResp['properties']['gridX']
            self.grid_y = pointsResp['properties']['gridY']
            self.forecast_office = pointsResp['properties']['cwa']
            self.county = pointsResp['properties']['county'].split('/')[-1]
            self.fire_zone = pointsResp['properties']['fireWeatherZone'].split('/')[-1]
        else:
            print(f"Sad honk :/ No NWS location details found for ({lat}, {lon})...")

    def afd_story(self, product: str) -> Story:
        rawGrafs = product['productText'].split('\n\n')
        grafs = ['<em>{}</em>'.format(rawGrafs[1].split('\n')[2])]
        for rawGraf in rawGrafs[2:]:
            graf = rawGraf.replace('\n', ' ').strip()
            match graf:
                case '&&':
                    grafs.append('<hr />')
                case '$$':
                    pass
                case _:
                    topic = re.match(r'\.?([\w/ ]+)\.\.\.', graf)
                    if topic is not None:
                        if topic.group(1).endswith('WATCHES/WARNINGS/ADVISORIES'):
                            # TODO: consume grafs, formatting XX..., until '&&'
                            grafs.append('<p><b>{}:</b> {}</p>'.format(topic.group(1), graf[topic.end():]))
                        else:
                            grafs.append('<p><b>{}:</b> {}</p>'.format(topic.group(1), graf[topic.end():]))
                    else:
                        grafs.append('<p>{}</p>'.format(graf))

        # remove any hanging section marker (which is likely)
        if grafs[-1] == '<hr />':
            grafs = grafs[:-1]

        return Story(
            product['productName'],
            body_html='<p>{}</p>'.format('</p><p>'.join(grafs))
        )

    def get_stories(self, limit: int = 5, **kwargs) -> List[Story]:
        # forecast
        if not hasattr(self, 'grid_x'):
            return []
        # perform three tries. api.weather.gov is a little flaky
        attempts = [1, 2, 3]
        ok = False
        for attempt in attempts:
            weatherResp = requests.get(
                    f"https://api.weather.gov/gridpoints/{self.forecast_office}/{self.grid_x},{self.grid_y}/forecast?units={self.units}"
            ).json()
            if weatherResp.get('properties'):
                ok = True
                break
            print('got a weird weatherResp on attempt {}: {}'.format(attempt, weatherResp))
        if not ok:
            print("couldn't get a good response in {} attempts... bailing.".format(attempts.len()))
        forecast = [
                '<p><b>{}:</b> {}</p>'.format(period['name'], period['detailedForecast'])
                    for period in weatherResp['properties']['periods']
        ]

        stories = [Story("Weather Forecast", body_html=''.join(forecast))]

        # products
        for productType in self.products:
            productsResp = requests.get(
                    f"https://api.weather.gov/products/types/{productType}/locations/{self.forecast_office}"
            ).json()
            if len(productsResp['@graph']) == 0:
                continue
            product = requests.get(productsResp['@graph'][0]['@id']).json()
            stories.append(
                self.afd_story(product) if productType == 'AFD' else Story(
                    product['productName'],
                    # FIXME: sadly, <pre> doesn't quite work in epub
                    body_html='<pre>{}</pre>'.format(product['productText'])
                )
            )

        # alerts
        alertResp = requests.get(
                f"https://api.weather.gov/alerts/active/zone/{self.county}"
        ).json()
        
        for alertBody in alertResp['features']:
            alert = alertBody['properties']
            if (self.county not in alert['geocode']['UGC']) and (self.fire_zone not in alert['geocode']['UGC']):
                continue

            stories.append(
                Story(
                    '{}: {}'.format(alert['response'], alert['event']),
                    body_html='<p>{}</p><p>{}</p><p>{}</p>'.format(
                        alert['headline'],
                        # TODO: fix `* FOO...` titles
                        '</p><p>'.join(alert['description'].split('\n\n')),
                        alert['instruction'],
                    ),
                    byline=alert['senderName']
                )
            )

        return stories
