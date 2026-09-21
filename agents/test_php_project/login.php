<?php

include "db.php";
include "utils.php";


function login($email, $password) {

    validatePassword($password);

    $user = getUserByEmail($email);


    if ($user && $user["password"] == $password) {

        return "Connexion réussie";

    } else {

        return "Email ou mot de passe incorrect";
    }
}



// Test

$email = "admin@test.com";
$password = "password123";


echo login($email, $password);

?>