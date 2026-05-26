from pathlib import Path

from hip_reader import CpioFormatError, read_entries

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hip" / "generated"


def test_reads_old_portable_cpio_records_without_padding() -> None:
    entries = list(read_entries(FIXTURES / "empty.hip"))

    assert entries[0].name == ".start"
    assert entries[0].header_offset == 0
    assert entries[3].name == ".takeconfig"
    assert entries[3].header_offset % 2 == 1
    assert entries[-1].name == ".cwd"
    assert len(entries) > 40


def test_reads_connected_fixture_records() -> None:
    names = [entry.name for entry in read_entries(FIXTURES / "box_wired_xform.hip")]

    assert "obj/geo1/box1.def" in names
    assert "obj/geo1/transform1.def" in names
    assert "obj/geo1.order" in names


def test_classifies_binary_locked_geometry_record() -> None:
    entries = {
        entry.name: entry for entry in read_entries(FIXTURES / "locked_geometry_or_stash.hip")
    }

    assert entries["obj/geo1/box1.data"].classification == "binary"
    assert entries["obj/geo1/box1.data"].size > 100


def test_classifies_takes_as_structured_binary() -> None:
    entries = {
        entry.name: entry for entry in read_entries(FIXTURES / "two_takes_changed_parm.hip")
    }

    assert entries[".takes"].classification == "take-data"


def test_rejects_non_cpio_file(tmp_path: Path) -> None:
    bogus = tmp_path / "not_a_hip.hip"
    bogus.write_bytes(b"not a hip")

    try:
        list(read_entries(bogus))
    except CpioFormatError as exc:
        assert "Expected old portable CPIO magic" in str(exc)
    else:
        raise AssertionError("Expected CpioFormatError")
