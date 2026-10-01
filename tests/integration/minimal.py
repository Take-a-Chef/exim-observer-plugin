#!/usr/bin/env python3
"""Exercise the real Exim binary and dynamic module using a private SMTP spool."""

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = "EHLO client.test\r\nMAIL FROM:<sender@example.test>\r\nRCPT TO:<one@observer.test>\r\nRCPT TO:<two@observer.test>\r\nDATA\r\nFrom: sender@example.test\r\nTo: one@observer.test, two@observer.test\r\nSubject: observer smoke\r\n\r\nhello\r\n.\r\nQUIT\r\n"


def integration_config(out):
    return f"""primary_hostname = observer.test
spool_directory = {out}/spool
log_file_path = {out}/log/%slog
exim_user = {os.getuid() or 65534}
exim_group = {os.getgid() if os.getuid() else 65534}
never_users = root
qualify_domain = observer.test
host_lookup =
rfc1413_query_timeout = 0s
deliver_drop_privilege = true
acl_smtp_rcpt = accept_all
observer_enabled = true
observer_events_socket = {out}/missing.sock
begin acl
accept_all:
  accept
begin routers
one:
  driver = accept
  local_parts = one
  transport = deliver_one
two:
  driver = accept
  local_parts = two
  transport = deliver_two
begin transports
deliver_one:
  driver = appendfile
  file = {out}/mail/one
  create_file = anywhere
  delivery_date_add
  envelope_to_add
  return_path_add
deliver_two:
  driver = appendfile
  file = {out}/mail/two
  create_file = anywhere
  delivery_date_add
  envelope_to_add
  return_path_add
begin retry
* * F,1h,5m
begin rewrite
begin authenticators
"""


def prepare_spool(out):
    for name in ("spool", "log", "mail"):
        p = out / name
        if p.exists():
            shutil.rmtree(p)
        p.mkdir()


def exim_runner(binary, out):
    def exim(args, input=None, expect_success=True):
        result = subprocess.run(
            [str(binary), *args],
            input=input,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        (out / "last-integration.log").write_text(result.stdout + "\n" + result.stderr)
        if (result.returncode == 0) != expect_success:
            raise AssertionError(
                f"{args}: exit {result.returncode}: {result.stdout}\n{result.stderr}"
            )
        return result

    return exim


def check_smtp_delivery(exim, out):
    result = exim(["-d+load", "-bs", "-odq"], SESSION)
    assert "Observer: module initialized" in result.stderr, result.stderr
    accepted = re.search(r"250 OK id=([A-Za-z0-9-]+)", result.stdout)
    assert accepted, result.stdout + "\n" + result.stderr
    message = accepted[1]
    headers = list((out / "spool/input").rglob(message + "-H"))
    assert len(headers) == 1
    content = headers[0].read_text()
    assert "one@observer.test" in content and "two@observer.test" in content
    # Exim executes its own normal delivery path; the plugin never starts another Exim.
    delivery = exim(["-d+load", "-M", message])
    assert delivery.stderr.count("Observer: native event msg:delivery") == 2
    assert "Observer: native event msg:complete" in delivery.stderr
    assert not headers[0].exists(), "message must complete normally with agent absent"
    assert (out / "mail/one").exists() and (out / "mail/two").exists()


def check_event_action(exim, out, config):
    # The hook also coexists with the administrator's native expansion listener.
    action = "${if eq{$event_name}{msg:complete}{observer-native-action}{}}"
    (out / "exim.conf").write_text("event_action = " + action + "\n" + config)
    result = exim(["-d+load", "-bs", "-odq"], SESSION)
    accepted = re.search(r"250 OK id=([A-Za-z0-9-]+)", result.stdout)
    assert accepted, result.stdout
    delivery = exim(["-d+load", "-M", accepted[1]])
    assert delivery.stderr.count("Observer: native event msg:delivery") == 2
    assert "Observer: native event msg:complete" in delivery.stderr
    assert 'event_action returned "observer-native-action"' in delivery.stderr, (
        delivery.stderr
    )


def check_config_syntax(exim, out, config, version):
    # Load/config syntax and disabled mode use the same native module table.
    (out / "exim.conf").write_text(
        config.replace("observer_enabled = true", "observer_enabled = false")
    )
    exim(["-bV"])
    (out / "exim.conf").write_text(config)
    # Singleton options must reject duplicates, including with the 4.100 parser.
    try:
        (out / "exim.conf").write_text("primary_hostname = duplicate.test\n" + config)
        duplicate = exim(["-bV"], expect_success=False)
        assert "option set for the second time" in duplicate.stderr, duplicate.stderr
        # Repeatable router conditions must remain accepted in both releases.
        (out / "exim.conf").write_text(
            config.replace(
                "  local_parts = one",
                "  local_parts = one\n  condition = yes\n  condition = yes",
            )
        )
        exim(["-bV"])
        # 4.100 adds repeatable headers_add strings as well as conditions.
        if version == "4.100.1":
            (out / "exim.conf").write_text(
                config.replace(
                    "  local_parts = one",
                    "  local_parts = one\n  headers_add = X-A: one\n  headers_add = X-B: two",
                )
            )
            exim(["-bV"])
    finally:
        (out / "exim.conf").write_text(config)


def main():
    if not __debug__:
        raise SystemExit(
            "Integration tests require assertions; unset PYTHONOPTIMIZE/remove -O"
        )
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["4.99.5", "4.100.1"], required=True)
    ap.add_argument("--cc", choices=["gcc", "clang"], required=True)
    a = ap.parse_args()
    if os.getuid() == 0:
        raise SystemExit("Run integration tests as an unprivileged user")
    out = ROOT / "build" / (a.version + "-" + a.cc)
    # The artifact paths are built into this test Exim; never invoke a system Exim.
    binary = out / "exim"
    prepare_spool(out)
    config = integration_config(out)
    (out / "exim.conf").write_text(config)
    exim = exim_runner(binary, out)
    version = exim(["-bV"])
    assert a.version in version.stdout
    check_smtp_delivery(exim, out)
    check_event_action(exim, out, config)
    check_config_syntax(exim, out, config, a.version)
    print(
        a.version,
        a.cc,
        "module loads; SMTP delivery and native event hooks pass with/without event_action; agent absent",
    )


if __name__ == "__main__":
    main()
