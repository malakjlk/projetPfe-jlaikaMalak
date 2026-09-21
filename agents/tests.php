<?php

class UserService
{
    private PDO $db;

    public function __construct(PDO $db)
    {
        $this->db = $db;
    }

    /**
     * Vérifie qu'un mot de passe respecte les règles minimales.
     */
    public function validatePassword(string $password): bool
    {
        if (strlen($password) < 8) {
            throw new Exception("Le mot de passe doit contenir au moins 8 caractères.");
        }

        return true;
    }

    /**
     * Recherche un utilisateur par son identifiant.
     */
    public function getUserById(int $id): ?array
    {
        $stmt = $this->db->prepare(
            "SELECT id, username, email FROM users WHERE id = :id"
        );

        $stmt->bindValue(":id", $id, PDO::PARAM_INT);
        $stmt->execute();

        $user = $stmt->fetch(PDO::FETCH_ASSOC);

        return $user ?: null;
    }

    /**
     * Crée un nouvel utilisateur.
     */
    public function createUser(
        string $username,
        string $email,
        string $password
    ): bool {

        $this->validatePassword($password);

        $hashedPassword = password_hash($password, PASSWORD_BCRYPT);

        $stmt = $this->db->prepare(
            "INSERT INTO users(username, email, password)
             VALUES(:username, :email, :password)"
        );

        return $stmt->execute([
            ":username" => $username,
            ":email" => $email,
            ":password" => $hashedPassword
        ]);
    }
}

?>