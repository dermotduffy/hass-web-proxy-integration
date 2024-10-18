"""Config flow for HASS Proxy."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_URLS, DOMAIN


class HASSProxyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,misc]
    """Config flow for HASS Proxy."""

    VERSION = 1

    @staticmethod
    @callback  # type: ignore[misc]
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HASSProxyOptionsFlowHandler:
        """Get the Frigate Options flow."""
        return HASSProxyOptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="HASS Proxy", data=user_input or {})


class HASSProxyOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Blueprint."""

    VERSION = 1

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize an options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URLS,
                        default=(user_input or {}).get(CONF_URLS, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            multiline=True,
                        ),
                    ),
                },
            ),
        )
