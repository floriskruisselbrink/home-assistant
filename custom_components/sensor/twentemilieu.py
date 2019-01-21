"""
Sensor component for Twentemilieu
Original Author:  Floris Kruisselbrink

Description:
  Provides sensors for the Dutch waste collector Twentemilieu.

Save the file as twentemilieu.py in [homeassistant]/config/custom_components/sensor/

resources options:
- GREY
- GREEN
- PAPER
- PACKAGES

Example config:
Configuration.yaml:
  sensor:
    - platform: twentemilieu
      resources:                       (at least 1 required)
        - GREY
        - GREEN
        - PAPER
        - PACKAGES
      postcode: 1111AA                 (required)
      streetnumber: 1                  (required)
"""

import logging
import requests
from datetime import datetime
from datetime import timedelta
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_RESOURCES)
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

__version__ = '1.0.0'

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(days=1)
CONF_POSTCODE = 'postcode'
CONF_STREETNUMBER = 'streetnumber'
SENSOR_PREFIX = 'Twentemilieu '

# keyword -> [name, unit, icon]
SENSOR_TYPES = {
    'GREY': ['Restafval', '', 'mdi:recycle'],
    'PAPER': ['Papier en karton', '', 'mdi:recycle'],
    'GREEN': ['Groente, fruit- en tuinafval', '', 'mdi:recycle'],
    'PACKAGES': ['PMD', '', 'mdi:recycle'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_POSTCODE, default='1111AA'): cv.string,
    vol.Required(CONF_STREETNUMBER, default='1'): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.debug('Setup Twentemilieu API retriever')

    postcode = config.get(CONF_POSTCODE)
    streetnumber = config.get(CONF_STREETNUMBER)

    try:
        data = WasteData(postcode, streetnumber)
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.upper()

        if sensor_type not in SENSOR_TYPES:
            SENSOR_TYPES[sensor_type] = [sensor_type.title(), '', 'mdi:recycle']

        entities.append(WasteSensor(data, sensor_type))

    add_entities(entities)


class WasteData(object):

    def __init__(self, postcode, streetnumber):
        self.data = None
        self.postcode = postcode
        self.streetnumber = streetnumber

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36',
                'Referer': 'https://www.twentemilieu.nl/enschede'
            }
            data = {
                'companyCode': '8d97bb56-5afd-4cbc-a651-b4f7314264b4',
                'postCode': self.postcode,
                'houseNumber': self.streetnumber
            }
            url = 'https://wasteapi.2go-mobile.com/api/FetchAdress'
            response = requests.post(url, headers=headers, data=data).json()
            if not response:
                _LOGGER.error('Address not found!')
            else:
                addresscode = response['dataList'][0]['UniqueId']
                startDate = datetime.now()
                endDate = startDate + timedelta(days=30)
                data = {
                    'companyCode': '8d97bb56-5afd-4cbc-a651-b4f7314264b4',
                    'uniqueAddressId': addresscode,
                    'startDate': startDate.strftime('%Y-%m-%d'),
                    'endDate': endDate.strftime("%Y-%m-%d")
                }
                url = 'https://wasteapi.2go-mobile.com/api/GetCalendar'
                requestjson = requests.post(url, headers=headers, data=data).json()
                sensordict = {}

                for trashType in requestjson['dataList']:
                    for pickupDate in trashType['pickupDates']:
                        sensorType=trashType['_pickupTypeText']
                        date = datetime.strptime(pickupDate[0:10], '%Y-%m-%d')

                        # only save nearest (oldest) date
                        if (not sensorType in sensordict) or (date < sensordict[sensorType]):
                            sensordict[sensorType] = date

                self.data = sensordict

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            self.data = None
            return False


class WasteSensor(Entity):

    def __init__(self, data, sensor_type):
        self.data = data
        self.type = sensor_type
        self._name = SENSOR_PREFIX + SENSOR_TYPES[self.type][0]
        self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit

    def update(self):
        self.data.update()
        wasteData = self.data.data
        keyword = self.type
        try:
            today = datetime.today()
            pickupdate = wasteData.get(keyword)
            
            if not pickupdate:
              _LOGGER.error('pickupdate null for keyword {}'.format(keyword))
              self._state = None
              return

            datediff = (pickupdate - today).days + 1

            if datediff >= 8:
                self._state = pickupdate.strftime('%d-%m-%Y')
            elif datediff > 1:
                self._state = pickupdate.strftime('%A, %d-%m-%Y')
            elif datediff == 1:
                self._state = pickupdate.strftime('Tomorrow, %d-%m-%Y')
            elif datediff == 0:
                self._state = pickupdate.strftime('Today, %d-%m-%Y')
            else:
                self._state = None

        except TypeError:
          _LOGGER.error('TypeError in WasteSensor.update()')  
          self._state = None
        except ValueError:
          _LOGGER.error('ValueError in WasteSensor.update()')  
          self._state = None
