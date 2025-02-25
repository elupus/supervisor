"""Test backups API."""

import asyncio
from pathlib import Path, PurePath
from unittest.mock import ANY, AsyncMock, patch

from aiohttp.test_utils import TestClient
from awesomeversion import AwesomeVersion
import pytest

from supervisor.backups.backup import Backup
from supervisor.const import CoreState
from supervisor.coresys import CoreSys
from supervisor.homeassistant.module import HomeAssistant
from supervisor.mounts.mount import Mount


async def test_info(api_client, coresys: CoreSys, mock_full_backup: Backup):
    """Test info endpoint."""
    resp = await api_client.get("/backups/info")
    result = await resp.json()
    assert result["data"]["days_until_stale"] == 30
    assert len(result["data"]["backups"]) == 1
    assert result["data"]["backups"][0]["slug"] == "test"
    assert result["data"]["backups"][0]["content"]["homeassistant"] is True
    assert len(result["data"]["backups"][0]["content"]["addons"]) == 1
    assert result["data"]["backups"][0]["content"]["addons"][0] == "local_ssh"


async def test_list(api_client, coresys: CoreSys, mock_full_backup: Backup):
    """Test list endpoint."""
    resp = await api_client.get("/backups")
    result = await resp.json()
    assert len(result["data"]["backups"]) == 1
    assert result["data"]["backups"][0]["slug"] == "test"
    assert result["data"]["backups"][0]["content"]["homeassistant"] is True
    assert len(result["data"]["backups"][0]["content"]["addons"]) == 1
    assert result["data"]["backups"][0]["content"]["addons"][0] == "local_ssh"


async def test_options(api_client, coresys: CoreSys):
    """Test options endpoint."""
    assert coresys.backups.days_until_stale == 30

    with patch.object(type(coresys.backups), "save_data") as save_data:
        await api_client.post(
            "/backups/options",
            json={
                "days_until_stale": 10,
            },
        )
        save_data.assert_called_once()

    assert coresys.backups.days_until_stale == 10


@pytest.mark.parametrize(
    "location,backup_dir",
    [("backup_test", PurePath("mounts", "backup_test")), (None, PurePath("backup"))],
)
async def test_backup_to_location(
    api_client: TestClient,
    coresys: CoreSys,
    location: str | None,
    backup_dir: PurePath,
    tmp_supervisor_data: Path,
    path_extern,
    mount_propagation,
):
    """Test making a backup to a specific location with default mount."""
    await coresys.mounts.load()
    (coresys.config.path_mounts / "backup_test").mkdir()
    mount = Mount.from_dict(
        coresys,
        {
            "name": "backup_test",
            "type": "cifs",
            "usage": "backup",
            "server": "backup.local",
            "share": "backups",
        },
    )
    await coresys.mounts.create_mount(mount)
    coresys.mounts.default_backup_mount = mount

    coresys.core.state = CoreState.RUNNING
    coresys.hardware.disk.get_disk_free_space = lambda x: 5000
    resp = await api_client.post(
        "/backups/new/full",
        json={
            "name": "Mount test",
            "location": location,
        },
    )
    result = await resp.json()
    assert result["result"] == "ok"
    slug = result["data"]["slug"]

    assert (tmp_supervisor_data / backup_dir / f"{slug}.tar").exists()

    resp = await api_client.get(f"/backups/{slug}/info")
    result = await resp.json()
    assert result["result"] == "ok"
    assert result["data"]["location"] == location


async def test_backup_to_default(
    api_client: TestClient,
    coresys: CoreSys,
    tmp_supervisor_data,
    path_extern,
    mount_propagation,
):
    """Test making backup to default mount."""
    await coresys.mounts.load()
    (mount_dir := coresys.config.path_mounts / "backup_test").mkdir()
    mount = Mount.from_dict(
        coresys,
        {
            "name": "backup_test",
            "type": "cifs",
            "usage": "backup",
            "server": "backup.local",
            "share": "backups",
        },
    )
    await coresys.mounts.create_mount(mount)
    coresys.mounts.default_backup_mount = mount

    coresys.core.state = CoreState.RUNNING
    coresys.hardware.disk.get_disk_free_space = lambda x: 5000
    resp = await api_client.post(
        "/backups/new/full",
        json={"name": "Mount test"},
    )
    result = await resp.json()
    assert result["result"] == "ok"
    slug = result["data"]["slug"]

    assert (mount_dir / f"{slug}.tar").exists()


async def test_api_freeze_thaw(
    api_client: TestClient,
    coresys: CoreSys,
    ha_ws_client: AsyncMock,
    tmp_supervisor_data,
    path_extern,
):
    """Test manual freeze and thaw for external backup via API."""
    coresys.core.state = CoreState.RUNNING
    coresys.hardware.disk.get_disk_free_space = lambda x: 5000
    ha_ws_client.ha_version = AwesomeVersion("2022.1.0")

    await api_client.post("/backups/freeze")
    assert coresys.core.state == CoreState.FREEZE
    await asyncio.sleep(0)
    assert any(
        call.args[0] == {"type": "backup/start"}
        for call in ha_ws_client.async_send_command.call_args_list
    )

    ha_ws_client.async_send_command.reset_mock()
    await api_client.post("/backups/thaw")
    assert coresys.core.state == CoreState.RUNNING
    await asyncio.sleep(0)
    assert any(
        call.args[0] == {"type": "backup/end"}
        for call in ha_ws_client.async_send_command.call_args_list
    )


@pytest.mark.parametrize(
    "partial_backup,exclude_db_setting",
    [(False, True), (True, True), (False, False), (True, False)],
)
async def test_api_backup_exclude_database(
    api_client: TestClient,
    coresys: CoreSys,
    partial_backup: bool,
    exclude_db_setting: bool,
    tmp_supervisor_data,
    path_extern,
):
    """Test backups exclude the database when specified."""
    coresys.core.state = CoreState.RUNNING
    coresys.hardware.disk.get_disk_free_space = lambda x: 5000
    coresys.homeassistant.version = AwesomeVersion("2023.09.0")
    coresys.homeassistant.backups_exclude_database = exclude_db_setting

    json = {} if exclude_db_setting else {"homeassistant_exclude_database": True}
    with patch.object(HomeAssistant, "backup") as backup:
        if partial_backup:
            resp = await api_client.post(
                "/backups/new/partial", json={"homeassistant": True} | json
            )
        else:
            resp = await api_client.post("/backups/new/full", json=json)

        backup.assert_awaited_once_with(ANY, True)
        assert resp.status == 200
