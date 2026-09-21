<?php
include("includes/db.php");
include("utils.php");

function login($email, $password) {
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new Exception("Email invalide");
    }
    $user = getUserByEmail($email);
    if ($user["password"] != hashPassword($password)) {
        throw new Exception("Identifiants incorrects");
    }
    return $user["id"];
}
