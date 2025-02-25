"""Home Assistant Supervisor setup."""
from setuptools import setup

from supervisor.const import SUPERVISOR_VERSION

setup(
    name="Supervisor",
    version=SUPERVISOR_VERSION,
    license="BSD License",
    author="The Home Assistant Authors",
    author_email="hello@home-assistant.io",
    url="https://home-assistant.io/",
    description=("Open-source private cloud os for Home-Assistant" " based on HassOS"),
    long_description=(
        "A maintainless private cloud operator system that"
        "setup a Home-Assistant instance. Based on HassOS"
    ),
    keywords=["docker", "home-assistant", "api"],
    zip_safe=False,
    platforms="any",
    packages=[
        "supervisor.addons",
        "supervisor.api",
        "supervisor.backups",
        "supervisor.dbus.network",
        "supervisor.dbus.network.setting",
        "supervisor.dbus",
        "supervisor.discovery.services",
        "supervisor.discovery",
        "supervisor.docker",
        "supervisor.homeassistant",
        "supervisor.host",
        "supervisor.jobs",
        "supervisor.misc",
        "supervisor.plugins",
        "supervisor.resolution.checks",
        "supervisor.resolution.evaluations",
        "supervisor.resolution.fixups",
        "supervisor.resolution",
        "supervisor.security",
        "supervisor.services.modules",
        "supervisor.services",
        "supervisor.store",
        "supervisor.utils",
        "supervisor",
    ],
    include_package_data=True,
)
