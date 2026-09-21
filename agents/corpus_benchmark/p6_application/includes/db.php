<?php
function getUserByEmail($email) {
    $sql = "SELECT * FROM users WHERE email=\"" . $email . "\"";
    $result = mysql_query($sql);
    return mysql_fetch_array($result);
}
