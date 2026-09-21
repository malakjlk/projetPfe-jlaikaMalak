<?php
function diviser($a, $b) {
    if ($b == 0) {
        throw new Exception("Division par zero");
    }
    return $a / $b;
}

function formaterPrix($montant) {
    if (!is_numeric($montant)) {
        throw new Exception("Montant invalide");
    }
    return number_format($montant, 2) . " EUR";
}

function calculerRemise($prix, $pourcentage) {
    if ($pourcentage < 0 || $pourcentage > 100) {
        throw new Exception("Pourcentage invalide");
    }
    return $prix - ($prix * $pourcentage / 100);
}
