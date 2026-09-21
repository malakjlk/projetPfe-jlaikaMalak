<?php
function getAllProducts() {
    $conn = mysql_connect("localhost", "root", "password123");
    mysql_select_db("shop", $conn);
    $result = mysql_query("SELECT * FROM products");
    $products = array();
    while ($row = mysql_fetch_array($result)) {
        $products[] = $row;
    }
    return $products;
}

function getProductById($id) {
    $sql = "SELECT * FROM products WHERE id=" . $id;
    $result = mysql_query($sql);
    return mysql_fetch_array($result);
}

function searchProducts($keyword) {
    $sql = "SELECT * FROM products WHERE name LIKE '%" . $keyword . "%'";
    $result = mysql_query($sql);
    $products = array();
    while ($row = mysql_fetch_array($result)) {
        $products[] = $row;
    }
    return $products;
}

function addProduct($name, $price, $stock) {
    if ($price <= 0) {
        throw new Exception('Prix invalide');
    }
    if ($stock < 0) {
        throw new Exception('Stock invalide');
    }
    $sql = "INSERT INTO products (name, price, stock) VALUES ('" . $name . "', " . $price . ", " . $stock . ")";
    mysql_query($sql);
}

function deleteProduct($id) {
    $sql = "DELETE FROM products WHERE id=" . $id;
    mysql_query($sql);
}
?>