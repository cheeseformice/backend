def search(a, t):
  l = 0
  r = len(a)-1
  while l <= r:
    m = (l + r) // 2
    print(m)
    if a[m] < t:
      l = m + 1
    elif a[m] > t:
      r = m
    else:
      return m
  return -1


print(search([6, 8], 7))