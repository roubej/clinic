from db.security import hash_password, password_error, verify_password


def test_password_hashes_use_unique_salts_and_verify_correct_password():
    first_salt, first_hash = hash_password("correct horse battery staple")
    second_salt, second_hash = hash_password("correct horse battery staple")

    assert first_salt != second_salt
    assert first_hash != second_hash
    assert verify_password("correct horse battery staple", first_salt, first_hash)
    assert not verify_password("wrong password", first_salt, first_hash)


def test_password_length_is_bounded():
    assert password_error("short") is not None
    assert password_error("a" * 129) is not None
    assert password_error("a" * 12) is None
