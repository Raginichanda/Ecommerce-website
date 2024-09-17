from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from .forms import CheckoutForm, CouponForm, RefundForm
from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon, Refund, Category
from django.contrib.auth.views import LoginView
import stripe
import random
import string

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

class PaymentView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if order.billing_address:
                context = {
                    'order': order,
                    'DISPLAY_COUPON_FORM': False
                }
                return render(self.request, "payment.html", context)
            else:
                messages.warning(self.request, "You have not added a billing address")
                return redirect("core:checkout")
        except Order.DoesNotExist:
            messages.error(self.request, "No active order found")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100)
        try:
            charge = stripe.Charge.create(
                amount=amount,
                currency="usd",
                source=token
            )
            payment = Payment.objects.create(
                stripe_charge_id=charge['id'],
                user=self.request.user,
                amount=order.get_total()
            )

            order.ordered = True
            order.payment = payment
            order.ref_code = create_ref_code()
            order.save()

            messages.success(self.request, "Order was successful")
            return redirect("/")

        except stripe.error.CardError as e:
            body = e.json_body
            err = body.get('error', {})
            messages.error(self.request, f"{err.get('message')}")
        except stripe.error.StripeError as e:
            messages.error(self.request, "Something went wrong with Stripe")
        except Exception as e:
            messages.error(self.request, "A serious error occurred")

        return redirect("/")

class HomeView(ListView):
    template_name = "index.html"
    queryset = Item.objects.filter(is_active=True)
    context_object_name = 'items'


class MyLoginView(LoginView):
    template_name = 'login.html'

class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except Order.DoesNotExist:
            messages.error(self.request, "You do not have an active order")
            return redirect("/")

class ShopView(ListView):
    model = Item
    paginate_by = 6
    template_name = "shop.html"

class ItemDetailView(DetailView):
    model = Item
    template_name = "product-detail.html"

class CategoryView(View):
    def get(self, *args, **kwargs):
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        items = Item.objects.filter(category=category, is_active=True)
        context = {
            'object_list': items,
            'category_title': category.title,
            'category_description': category.description,
            'category_image': category.image
        }
        return render(self.request, "category.html", context)

class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }
            return render(self.request, "checkout.html", context)
        except Order.DoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                zip = form.cleaned_data.get('zip')
                payment_option = form.cleaned_data.get('payment_option')

                billing_address = BillingAddress.objects.create(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip=zip,
                    address_type='B'
                )
                order.billing_address = billing_address
                order.save()

                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                else:
                    messages.warning(self.request, "Invalid payment option selected")
        except Order.DoesNotExist:
            messages.error(self.request, "You do not have an active order")

        return redirect('core:checkout')

@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "Item quantity was updated.")
        else:
            order.items.add(order_item)
            messages.info(request, "Item was added to your cart.")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date
        )
        order.items.add(order_item)
        messages.info(request, "Item was added to your cart.")
    
    return redirect("core:order-summary")

@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            ).first()
            if order_item:
                order.items.remove(order_item)
                messages.info(request, "Item was removed from your cart.")
        else:
            messages.info(request, "Item was not in your cart.")
    else:
        messages.info(request, "You don't have an active order.")
    
    return redirect("core:product", slug=slug)

@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            ).first()
            if order_item:
                if order_item.quantity > 1:
                    order_item.quantity -= 1
                    order_item.save()
                else:
                    order.items.remove(order_item)
                messages.info(request, "Item quantity was updated.")
        else:
            messages.info(request, "Item was not in your cart.")
    else:
        messages.info(request, "You don't have an active order.")
    
    return redirect("core:product", slug=slug)

def get_coupon(request, code):
    try:
        return Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        messages.info(request, "This coupon does not exist")
        return None

class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            code = form.cleaned_data.get('code')
            try:
                coupon = get_coupon(self.request, code)
                if coupon:
                    order = Order.objects.get(
                        user=self.request.user, ordered=False
                    )
                    order.coupon = coupon
                    order.save()
                    messages.success(self.request, "Successfully added coupon")
            except Order.DoesNotExist:
                messages.info(self.request, "You do not have an active order")

        return redirect("core:checkout")

class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        return render(self.request, "request_refund.html", {'form': form})

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                Refund.objects.create(
                    order=order,
                    reason=message,
                    email=email
                )

                messages.info(self.request, "Your request was received")
            except Order.DoesNotExist:
                messages.info(self.request, "This order does not exist")

        return redirect("core:request-refund")
