"""Config flow for HASS Web Proxy."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DYNAMIC_URLS,
    CONF_SSL_CIPHERS,
    CONF_SSL_CIPHERS_DEFAULT,
    CONF_SSL_CIPHERS_INSECURE,
    CONF_SSL_CIPHERS_INTERMEDIATE,
    CONF_SSL_CIPHERS_MODERN,
    CONF_SSL_VERIFICATION,
    CONF_URL_PATTERNS,
    DEFAULT_OPTIONS,
    DOMAIN,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_URL_PATTERNS,
        ): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(
            CONF_SSL_VERIFICATION,
        ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
        vol.Optional(
            CONF_SSL_CIPHERS,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    CONF_SSL_CIPHERS_DEFAULT,
                    CONF_SSL_CIPHERS_MODERN,
                    CONF_SSL_CIPHERS_INTERMEDIATE,
                    CONF_SSL_CIPHERS_INSECURE,
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_SSL_CIPHERS,
            )
        ),
        vol.Optional(
            CONF_DYNAMIC_URLS,
        ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
    },
)


class HASSWebProxyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,misc]
    """Config flow for HASS Web Proxy."""

    @staticmethod
    @callback  # type: ignore[misc]
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HASSWebProxyOptionsFlowHandler:
        """Get the Frigate Options flow."""
        return HASSWebProxyOptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title="Home Assistant Web Proxy",
            data=user_input or {},
            options=DEFAULT_OPTIONS,
        )


class HASSWebProxyOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Blueprint."""

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
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self._config_entry.options
            ),
        )
