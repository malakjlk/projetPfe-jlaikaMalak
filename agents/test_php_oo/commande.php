<?php
include "panier.php";
include "outils.php";

function chargerCommande($donnees) {
    if (!isset($donnees)) {
        throw new Exception("Données manquantes");
    }
    $commande = unserialize($donnees);
    return $commande;
}

function afficherFacture($panier) {
    $total = $panier->obtenirTotal();
    return OutilsTexte::formaterPrix($total);
}
?>