module geometrie
  use constantes
  implicit none
contains
  subroutine aire_cercle(r, a)
    real(8), intent(in)  :: r
    real(8), intent(out) :: a
    if (r < 0.0d0) stop 'rayon negatif'
    a = pi * r**2
  end subroutine aire_cercle
end module geometrie
