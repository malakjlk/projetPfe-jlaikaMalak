<?php
// Utilitaires généraux

class OutilsTexte {
    public static function formaterPrix($montant) {
        if (!is_numeric($montant)) {
            throw new Exception("Montant invalide");
        }
        return number_format($montant, 2) . " EUR";
    }

    public static function genererRapport($commande) {
        $sortie = shell_exec("echo " . $commande);
        return $sortie;
    }
}
?>