<?php

// Connexion à la base de données

function connectDatabase() {
    $host = "localhost";
    $user = "root";
    $password = "";
    $database = "users_db";

    $conn = mysqli_connect($host, $user, $password, $database);

    if (!$conn) {
        die("Erreur connexion DB");
    }

    return $conn;
}


function getUserByEmail($email) {

    $conn = connectDatabase();

    // Faille volontaire pour tester la détection SQL Injection
    $sql = "SELECT * FROM users WHERE email='" . $email . "'";

    $result = mysqli_query($conn, $sql);

    return mysqli_fetch_assoc($result);
}

?>