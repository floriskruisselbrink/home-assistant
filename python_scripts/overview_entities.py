count_all = 0
domains = []
attributes = {}

for entity_id in hass.states.entity_ids():
  count_all = count_all + 1
  entity_domain = entity_id.split('.')[0]
  if entity_domain not in domains:
    domains.append(entity_domain)

for domain in sorted(domains):
  attributes[domain] = len(hass.states.entity_ids(domain))

attributes['friendly_name'] = 'Entities'
attributes['icon'] = 'mdi:format-list-numbered'

hass.states.set('sensor.overview_entities', count_all, attributes)
