<?php
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception("Mot de passe trop court");
    }
    if (!preg_match("/[A-Z]/", $password)) {
        throw new Exception("Majuscule requise");
    }
    return true;
}

function validerEmail($email) {
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new Exception("Email invalide");
    }
    return true;
}

function validerAge($age) {
    if (!is_numeric($age)) {
        throw new Exception("Age non numerique");
    }
    if ($age < 18) {
        throw new Exception("Doit etre majeur");
    }
    return true;
}
