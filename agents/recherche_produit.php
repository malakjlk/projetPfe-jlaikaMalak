<?php
/**
 * Recherche de produit — code legacy vulnérable.
 * Contient une injection SQL (CWE-89) que la migration
 * doit corriger, et un invariant de longueur à préserver.
 */
function chercherProduit($nom) {

    // Invariant : la recherche exige au moins 3 caracteres
    if (strlen($nom) < 3) {
        throw new Exception('Recherche trop courte');
    }

    // VULNERABILITE : concatenation directe dans la requete
    $sql = "SELECT * FROM produits WHERE nom LIKE '%" . $nom . "%'";
    $resultat = mysql_query($sql);

    return mysql_fetch_array($resultat);
}
