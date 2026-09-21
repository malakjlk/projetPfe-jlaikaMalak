<?php
class PanierAchat {
    private $articles = array();
    private $total = 0;

    public function ajouterArticle($nom, $prix) {
        if ($prix < 0) {
            throw new Exception("Prix negatif");
        }
        $this->articles[] = $nom;
        $this->total += $prix;
        return true;
    }

    public function obtenirTotal() {
        return $this->total;
    }
}

class OutilsTexte {
    public static function majuscules($texte) {
        return strtoupper($texte);
    }

    public static function tronquer($texte, $longueur) {
        if ($longueur < 1) {
            throw new Exception("Longueur invalide");
        }
        return substr($texte, 0, $longueur);
    }
}
