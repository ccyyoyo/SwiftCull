from app.db.group_repository import GroupRepository
from app.db.photo_repository import PhotoRepository
from app.core.models import Photo


def _insert_photo(repo, path):
    return repo.insert(Photo(id=None, relative_path=path, filename=path, file_size=1))


def test_create_group_returns_id(db_conn):
    repo = GroupRepository(db_conn)
    gid = repo.create_group("Test Group", "similar")
    assert isinstance(gid, int)
    assert gid > 0


def test_get_groups_by_type(db_conn):
    repo = GroupRepository(db_conn)
    repo.create_group("G1", "similar")
    repo.create_group("G2", "similar")
    repo.create_group("B1", "burst")
    groups = repo.get_groups_by_type("similar")
    assert len(groups) == 2
    assert all(g.type == "similar" for g in groups)


def test_add_photo_to_group(db_conn):
    photo_repo = PhotoRepository(db_conn)
    pid = _insert_photo(photo_repo, "a.jpg")
    grp_repo = GroupRepository(db_conn)
    gid = grp_repo.create_group(None, "similar")
    grp_repo.add_photo_to_group(pid, gid)
    members = grp_repo.get_photo_ids_in_group(gid)
    assert pid in members


def test_get_photo_ids_in_group_empty(db_conn):
    repo = GroupRepository(db_conn)
    gid = repo.create_group(None, "similar")
    assert repo.get_photo_ids_in_group(gid) == []


def test_count_photos_in_group(db_conn):
    photo_repo = PhotoRepository(db_conn)
    p1 = _insert_photo(photo_repo, "x.jpg")
    p2 = _insert_photo(photo_repo, "y.jpg")
    repo = GroupRepository(db_conn)
    gid = repo.create_group(None, "similar")
    repo.add_photo_to_group(p1, gid)
    repo.add_photo_to_group(p2, gid)
    assert repo.count_photos_in_group(gid) == 2


def test_clear_groups_by_type_removes_groups_and_memberships(db_conn):
    photo_repo = PhotoRepository(db_conn)
    pid = _insert_photo(photo_repo, "z.jpg")
    repo = GroupRepository(db_conn)
    gid = repo.create_group("tbd", "similar")
    repo.add_photo_to_group(pid, gid)

    repo.clear_groups_by_type("similar")

    assert repo.get_groups_by_type("similar") == []
    assert repo.get_photo_ids_in_group(gid) == []


def test_clear_groups_does_not_affect_other_types(db_conn):
    repo = GroupRepository(db_conn)
    repo.create_group("burst1", "burst")
    repo.create_group("sim1", "similar")
    repo.clear_groups_by_type("similar")
    bursts = repo.get_groups_by_type("burst")
    assert len(bursts) == 1


def test_get_group_id_for_photo(db_conn):
    photo_repo = PhotoRepository(db_conn)
    pid = _insert_photo(photo_repo, "q.jpg")
    repo = GroupRepository(db_conn)
    gid = repo.create_group(None, "similar")
    repo.add_photo_to_group(pid, gid)
    assert repo.get_group_id_for_photo(pid, "similar") == gid
    assert repo.get_group_id_for_photo(pid, "burst") is None


def test_set_best_in_group(db_conn):
    photo_repo = PhotoRepository(db_conn)
    p1 = _insert_photo(photo_repo, "best1.jpg")
    p2 = _insert_photo(photo_repo, "best2.jpg")
    repo = GroupRepository(db_conn)
    gid = repo.create_group(None, "similar")
    repo.add_photo_to_group(p1, gid, is_best=False)
    repo.add_photo_to_group(p2, gid, is_best=False)
    repo.set_best_in_group(p1, gid)
    members = repo.get_photo_ids_in_group(gid)
    assert members[0] == p1  # is_best DESC → p1 first


def test_phash_hash_stored_in_photo(db_conn):
    photo_repo = PhotoRepository(db_conn)
    pid = _insert_photo(photo_repo, "h.jpg")
    photo_repo.update_phash_hash(pid, "deadbeefcafe1234")
    photo = photo_repo.get_by_id(pid)
    assert photo.phash_hash == "deadbeefcafe1234"


def test_get_phash_unanalyzed_ids(db_conn):
    photo_repo = PhotoRepository(db_conn)
    p1 = _insert_photo(photo_repo, "u1.jpg")
    p2 = _insert_photo(photo_repo, "u2.jpg")
    photo_repo.update_phash_hash(p1, "0000000000000000")
    unanalyzed = photo_repo.get_phash_unanalyzed_ids()
    assert p2 in unanalyzed
    assert p1 not in unanalyzed


def test_get_all_phash_hashes(db_conn):
    photo_repo = PhotoRepository(db_conn)
    p1 = _insert_photo(photo_repo, "h1.jpg")
    p2 = _insert_photo(photo_repo, "h2.jpg")
    _insert_photo(photo_repo, "h3.jpg")  # no hash
    photo_repo.update_phash_hash(p1, "aabbccddeeff0011")
    photo_repo.update_phash_hash(p2, "1122334455667788")
    result = photo_repo.get_all_phash_hashes()
    assert result[p1] == "aabbccddeeff0011"
    assert result[p2] == "1122334455667788"
    assert len(result) == 2
