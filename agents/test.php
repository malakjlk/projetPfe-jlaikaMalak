<?php
function validateUser($username, $password) {
    if (strlen($username) < 3) {
        throw new Exception('Username trop court');
    }
    if (strlen($password) < 8) {
        throw new Exception('Password trop court');
    }
    if (!preg_match('/[A-Z]/', $password)) {
        throw new Exception('Majuscule requise');
    }
    return true;
}

function getUserById($id) {
    $sql = "SELECT * FROM users WHERE id=" . $id;
    $result = mysql_query($sql);
    return mysql_fetch_array($result);
}

function deleteUser($id) {
    $sql = "DELETE FROM users WHERE id=" . $id;
    mysql_query($sql);
}
?>