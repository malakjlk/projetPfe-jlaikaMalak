<?php
/**
 * Validation d'inscription utilisateur — code legacy.
 * Fonction pure : entièrement vérifiable par test différentiel
 * et par exécution symbolique.
 */
function validerInscription($pseudo, $age) {

    // Invariant 1 : longueur minimale du pseudo
    if (strlen($pseudo) < 4) {
        throw new Exception('Pseudo trop court');
    }

    // Invariant 2 : longueur maximale du pseudo
    if (strlen($pseudo) > 20) {
        throw new Exception('Pseudo trop long');
    }

    // Invariant 3 : format du pseudo (lettres, chiffres, tiret bas)
    if (!preg_match('/^[a-zA-Z0-9_]+$/', $pseudo)) {
        throw new Exception('Caracteres non autorises');
    }

    // Invariant 4 : l'age doit etre numerique
    if (!is_numeric($age)) {
        throw new Exception('Age non numerique');
    }

    // Invariant 5 : majorite requise
    if ($age < 18) {
        throw new Exception('Inscription reservee aux majeurs');
    }

    return true;
}
