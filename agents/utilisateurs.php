<?php
class User {
    protected $nom;
    public function obtenirNom() { return $this->nom; }
}
class Admin extends User {
    public function bannirUtilisateur($id) {
        if (strlen($id) < 1) { throw new Exception("ID invalide"); }
        return true;
    }
}
?>