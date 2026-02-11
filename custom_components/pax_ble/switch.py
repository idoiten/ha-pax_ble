import logging
from collections import namedtuple
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_NAME
from .const import DeviceModel
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

PaxAttribute = namedtuple("PaxAttribute", ["key", "descriptor", "unit"])
boostmode_attribute = PaxAttribute("boostmodesecread", "Boost time remaining", " s")

PaxEntity = namedtuple(
    "PaxEntity", ["key", "entityName", "category", "icon", "attributes"]
)
ENTITIES = [
    PaxEntity("boostmode", "BoostMode", None, "mdi:wind-power", boostmode_attribute),
]
CALIMA_ENTITIES = [
    PaxEntity(
        "trickledays_weekdays",
        "TrickleDays Weekdays",
        EntityCategory.CONFIG,
        "mdi:calendar",
        None,
    ),
    PaxEntity(
        "trickledays_weekends",
        "TrickleDays Weekends",
        EntityCategory.CONFIG,
        "mdi:calendar",
        None,
    ),
    PaxEntity(
        "silenthours_on",
        "SilentHours On",
        EntityCategory.CONFIG,
        "mdi:volume-off",
        None,
    ),
]
SVENSA_ENTITIES = [
    PaxEntity(
        "trickle_on", "Trickle On", EntityCategory.CONFIG, "mdi:volume-off", None
    ),
    PaxEntity(
        "pause", "Pause", None, "mdi:pause", None
    ),
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup switch from a config entry created in the integrations UI."""
    ha_entities = []

    for device_id in config_entry.data[CONF_DEVICES]:
        _LOGGER.debug(
            "Starting paxcalima switches: %s",
            config_entry.data[CONF_DEVICES][device_id][CONF_NAME],
        )

        coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DEVICES][device_id]

        for paxentity in ENTITIES:
            ha_entities.append(PaxCalimaSwitchEntity(coordinator, paxentity))

        match coordinator._model:
            case (
                DeviceModel.CALIMA.value
                | DeviceModel.SVARA.value
                | DeviceModel.LEVANTE.value
            ):
                for paxentity in CALIMA_ENTITIES:
                    ha_entities.append(PaxCalimaSwitchEntity(coordinator, paxentity))
            case DeviceModel.SVENSA.value:
                for paxentity in SVENSA_ENTITIES:
                    ha_entities.append(PaxCalimaSwitchEntity(coordinator, paxentity))

    async_add_devices(ha_entities, True)


class PaxCalimaSwitchEntity(PaxCalimaEntity, SwitchEntity):
    """Representation of a Switch."""

    def __init__(self, coordinator, paxentity):
        super().__init__(coordinator, paxentity)
        self._paxattr = paxentity.attributes

    @property
    def is_on(self):
        """Return the state of the switch."""
        return self.coordinator.get_data(self._key)

    @property
    def extra_state_attributes(self):
        if self._paxattr is not None:
            descriptor = self._paxattr.descriptor
            key = self.coordinator.get_data(self._paxattr.key)
            unit = self._paxattr.unit
            attrs = {descriptor: str(key) + unit}
            attrs.update(super().extra_state_attributes)
            return attrs
        else:
            return None

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug("Enabling %s", self._attr_name)
        await self.writeVal(1)

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug("Disabling %s", self._attr_name)
        await self.writeVal(0)

    async def writeVal(self, val):
        """Write a value to the device with immediate state refresh."""
        old_value = self.coordinator.get_data(self._key)

        # Sätt nytt värde lokalt
        self.coordinator.set_data(self._key, val)

        # Skriv till enheten
        ret = await self.coordinator.write_data(self._key)

        if not ret:
            # Återställ vid misslyckande
            self.coordinator.set_data(self._key, old_value)

        # --- Direkt läsning av värde från fläkten ---
        if hasattr(self.coordinator, "read_sensordata"):
            await self.coordinator.read_sensordata(disconnect=False)

        # Uppdatera HA med det färska värdet
        self.async_schedule_update_ha_state(force_refresh=True)
