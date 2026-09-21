<?php
class User {
    private $nom;
    private $email;

    public function obtenirNom() {
        return $this->nom;
    }
}

class Admin extends User {
    public function bannirUtilisateur($id) {
        if (strlen($id) < 1) {
            throw new Exception("ID invalide");
        }
        return true;
    }
}

class SuperAdmin extends Admin {
    public function supprimerCompte($id) {
        if (!is_numeric($id)) {
            throw new Exception("ID non numerique");
        }
        return true;
    }
}
