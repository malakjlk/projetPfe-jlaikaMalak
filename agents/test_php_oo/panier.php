<?php
// Gestion du panier d'achat

class PanierAchat {
    private $articles;
    private $total;

    public function ajouterArticle($nom, $prix) {
        if ($prix < 0) {
            throw new Exception("Prix invalide");
        }
        if (strlen($nom) < 2) {
            throw new Exception("Nom d'article trop court");
        }
        $this->articles[] = $nom;
        $this->total += $prix;
        return true;
    }

    public function obtenirTotal() {
        return $this->total;
    }

    public function viderPanier() {
        $this->articles = array();
        $this->total = 0;
    }
}
?>