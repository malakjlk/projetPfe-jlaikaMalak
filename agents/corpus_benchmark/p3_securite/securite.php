<?php
function getUser($id) {
    $sql = "SELECT * FROM users WHERE id=" . $id;
    $result = mysql_query($sql);
    return mysql_fetch_array($result);
}

function genererRapport($commande) {
    $sortie = shell_exec("report_tool " . $commande);
    return $sortie;
}

function chercherProduit($nom) {
    $sql = "SELECT * FROM produits WHERE nom LIKE \"%" . $nom . "%\"";
    return mysql_query($sql);
}
