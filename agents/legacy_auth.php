<?php
function loginUser($username, $password) {
    $conn = mysql_connect("localhost", "root", "password123");
    mysql_select_db("myapp", $conn);
    
    $sql = "SELECT * FROM users WHERE username='" . $username . "' AND password='" . $password . "'";
    $result = mysql_query($sql);
    
    if (mysql_num_rows($result) > 0) {
        $user = mysql_fetch_array($result);
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['username'] = $user['username'];
        $_SESSION['logged_in'] = true;
        return true;
    }
    return false;
}

function logoutUser() {
    session_start();
    session_destroy();
    header('Location: login.php');
}

function checkLogin() {
    session_start();
    if (!isset($_SESSION['logged_in']) || $_SESSION['logged_in'] !== true) {
        header('Location: login.php');
        exit();
    }
}

function changePassword($userId, $oldPassword, $newPassword) {
    if (strlen($newPassword) < 6) {
        return false;
    }
    $conn = mysql_connect("localhost", "root", "password123");
    $sql = "UPDATE users SET password='" . $newPassword . "' WHERE id=" . $userId;
    mysql_query($sql);
    return true;
}
?>