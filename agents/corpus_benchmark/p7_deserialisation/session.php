<?php
function chargerSession($data) {
    $session = unserialize($data);
    return $session;
}

function afficherPage($page) {
    include($page . ".php");
}

function sauvegarderPreferences($prefs) {
    if (empty($prefs)) {
        throw new Exception("Preferences vides");
    }
    return serialize($prefs);
}
