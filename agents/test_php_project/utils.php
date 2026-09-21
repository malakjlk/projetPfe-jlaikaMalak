<?php

// Fonctions utilitaires

function validatePassword($password) {

    if (strlen($password) < 8) {
        throw new Exception("Mot de passe trop court");
    }

    return true;
}


function sanitizeInput($data) {

    return htmlspecialchars($data);
}

?>