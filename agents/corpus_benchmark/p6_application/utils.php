<?php
function hashPassword($password) {
    if (strlen($password) < 8) {
        throw new Exception("Trop court");
    }
    return password_hash($password, PASSWORD_DEFAULT);
}
